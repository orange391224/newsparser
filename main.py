# git clone <url> --branch <branch> --single-branch <folder>
# git clone ssh://git@80.211.171.112/~/newsparser-rostech.git --branch dev --single-branch newsparser-dev
# git clone ssh://git@80.211.171.112/~/newsparser-rostech.git --branch master --single-branch newsparser-prod

import datetime
import os
import tkinter as tk
from tkinter.messagebox import showinfo, showerror
import traceback
from shutil import copyfile
import logging
from glob import glob
import configparser
import sys

import pygubu  # pygubu-designer
from newspaper import Article
from peewee import *
from playhouse.sqlite_ext import Proxy
from readability import Document
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlsplit
from docxtpl import Listing

import render_docx
import urlhandlers
import articleDateExtractor
import gettabs

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
elif __file__:
    application_path = os.path.dirname(__file__)
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(CURRENT_DIR, 'templates')

database_proxy = Proxy()
LOG_FILENAME = os.path.join(application_path, 'messages.log')
logging.basicConfig(filename=LOG_FILENAME, level=logging.DEBUG)
logger = logging.getLogger('logs_transfer')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(LOG_FILENAME)
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)


SELECTED_TEMPLATE = ''
START = True
FULL_TEXT = False
prog_title = 'Обзорщик 3.2.1 dev'


#############База данных - модель########################
class row(Model):
    title = CharField()
    text = TextField()
    section = CharField()
    pubdate = CharField()
    mass_media = CharField()
    order_id = IntegerField()
    url = CharField()
    fulltext=TextField()
    current_show_p=IntegerField()
    class Meta:
        database = database_proxy


#############База данных###################################
class DbWorker:
    def __init__(self):
        # db.connect()
        db = SqliteDatabase(SELECTED_TEMPLATE + '\\database.db')
        db.create_tables([row])

    def insert(self, section, title, date, mass_media, text, url,fulltext,current_show_p):
        try:
            last_row = row.select().where(row.section == section).order_by(row.order_id.desc()).get()
            order_id = last_row.order_id + 1
        except:
            order_id = 1

        attach = row(title=title.rstrip(), section=section, text=text,
                     pubdate=date, mass_media=mass_media,
                     url=url,
                     order_id=order_id,
                     fulltext=fulltext,
                     current_show_p=current_show_p)
        attach.save()

    def delete(self, id):
        if isinstance(id, int):
            query = row.select().where(row.id == id).get()
            query.delete_instance()
        else:
            # Вывести, что раздел удалять нельзя
            pass

    @staticmethod
    def get_sections():
        global SELECTED_TEMPLATE
        returnlist = []
        try:
            if not SELECTED_TEMPLATE:
                SELECTED_TEMPLATE = TEMPLATES_DIR + '\\Вечерний обзор Ростех'
            with open(os.path.join(SELECTED_TEMPLATE, 'sections.txt'), 'r') as myfile:
                data = myfile.read().split('\n')
            for section in data:
                # Заполняем Разделами
                returnlist.append(section)
            return returnlist
        except:
            logger.exception('Ошибка при чтении sections.txt')

    def get_article_by_id(self, id):
        query = row.get(row.id == id)
        d_article = {'title': query.title,
                     'text': query.text,
                     'pubdate': query.pubdate,
                     'mass_media': query.mass_media,
                     'url': query.url,
                     'fulltext': query.fulltext,
                     'curr_show_p': query.current_show_p
                     }
        return d_article

    def update_id(self, id, direction):
        s_row = row.select().where(row.id == id).get()
        s_id = s_row.id
        s_order_id = s_row.order_id
        s_section = s_row.section

        if direction == 'up':
            if s_row.order_id == 1:
                # Значит элемент на самом верху - делать ничего не нужно
                return
            else:
                # Элемент выше нужно опустить, т.е. увеличить order_id
                q = row.select().where((row.order_id == s_order_id - 1) & (row.section == s_section)).get()
                q.order_id = q.order_id + 1
                q.save()
                # Выбранный поднять, т.е. уменьшить order_id
                q = row.select().where(row.id == s_id).get()
                q.order_id = q.order_id - 1
                q.save()

        if direction == 'down':
            # Нужно проверить не достигли ли мы дна
            count = row.select().where(row.section == s_section).count()
            if s_row.order_id == count:
                # снизу уже не постучат
                return
            else:
                # Элемент ниже нужно поднять, т.е. уменьшить order_id
                q = row.select().where((row.order_id == s_order_id + 1) & (row.section == s_section)).get()
                q.order_id = q.order_id - 1
                q.save()
                # Выбранный опустить, т.е. увеличить order_id
                q = row.select().where(row.id == s_id).get()
                q.order_id = q.order_id + 1
                q.save()

    def update_row(self, id, url, title, date, mass_media, text,curr_show_p):
        q = row.select().where(row.id == id).get()
        q.url = url
        q.title = title
        q.pubdate = date
        q.mass_media = mass_media
        q.text = text
        q.current_show_p = curr_show_p
        q.save()

    def change_section(self,id,section):
        #ToDO: при перемещении нужно пересчитывать order_id!

        q = row.select().where(row.id == id).get()
        q.section = section
        # Нужно посчитать сколько сейчас элементов в секции
        count = row.select().where(row.section == section).count()
        q.order_id = count+1
        q.save()

##################################################

class DialogSelectTemplate:
    """Диалог выбора варианта оформления docx файла"""

    def __init__(self, parent):
        top = self.top = tk.Toplevel(parent)
        self.myLabel = tk.Label(top, text='Выберите необходимый шаблон')

        self.myLabel.pack()

        # self.myEntryBox = tk.Entry(top)
        # self.myEntryBox.pack()
        self.lbox = tk.Listbox(top, width=60)
        self.lbox.pack()
        templates = glob(TEMPLATES_DIR + '/*')
        for template in templates:
            self.lbox.insert(0, os.path.basename(template))

        self.mySubmitButton = tk.Button(top, text='Выбрать', command=self.send)
        self.mySubmitButton.pack()
        self.top.focus_set()
        self.top.transient(parent)

    def send(self):
        self.selected_template = self.lbox.get(tk.ACTIVE)
        self.top.destroy()

class DialogChangeSection:
    """Диалог выбора раздела новости"""

    def __init__(self, parent):
        top = self.top = tk.Toplevel(parent)
        self.myLabel = tk.Label(top, text='Выберите необходимый раздел')

        self.myLabel.pack()

        self.lbox = tk.Listbox(top, width=60)
        self.lbox.pack()

        dbworker = DbWorker()
        sections = dbworker.get_sections()

        for section in sections:
            self.lbox.insert(0, os.path.basename(section))

        self.mySubmitButton = tk.Button(top, text='Сменить', command=self.send)
        self.mySubmitButton.pack()
        self.top.focus_set()
        self.top.transient(parent)

    def send(self):
        self.selected_section = self.lbox.get(tk.ACTIVE)
        self.top.destroy()


class Myarticle(Article):
    def __init__(self, url):
        super().__init__(url, language='ru')
        self.mass_media = ''
        self.paragraphs = []
        self.url = url

    def postprocessing(self, handle=True):
        if handle:
            handl = urlhandlers.handle_by_url(self)
            self.mass_media = handl['izd_name']
            self.publish_date = handl['pubdate']
            self.text = handl['news_text']
            self.title = handl['news_title']

        self.fulltext = self.text

        if not FULL_TEXT:
            self.paragraphs = self.text.split('\n')
            self.text = self.paragraphs[0]

        if not self.publish_date:
            self.publish_date = articleDateExtractor.extractArticlePublishedDate(self.url, self.html)


        if not isinstance(self.publish_date,str) and self.publish_date:
            publish_date = self.publish_date
            self.publish_date = str(publish_date.day) + '.0' + str(publish_date.month) + '.' + str(publish_date.year)

        if not self.mass_media:
            clean_path = urlsplit(self.url)
            base_url = clean_path.netloc
            self.mass_media = base_url.replace('www.', '')

    def get_pubdate(self):
        if self.publish_date:
            return self.publish_date
        else:
            return ''

    def get_title(self):
        return self.title.rstrip()

    def get_text(self):
        return self.text.rstrip()

    def get_full_text(self):
        return self.fulltext.rstrip()

    def get_mass_media(self):
        return self.mass_media.rstrip()

    def get_paragraphs(self):
        return self.paragraphs

    def load_alt_engine(self):
        response = requests.get(self.url)
        doc = Document(response.text)
        txt = doc.summary()

        soup = BeautifulSoup(txt, 'html.parser')
        self.text = soup.get_text()
        self.html = response.text
        self.title = doc.short_title()

class Application(pygubu.TkApplication):

    def __init__(self, master):
        super().__init__(master)
        global SELECTED_TEMPLATE
        global START

        self.builder = builder = pygubu.Builder()
        builder.add_from_file(os.path.join(CURRENT_DIR, 'gui.ui'))
        self.mainwindow = builder.get_object('mainwindow')
        self.toplevel = self.mainwindow.winfo_toplevel()
        self.set_title(prog_title)
        self.set_resizable()
        self.fulltext = ''
        # Меню
        root = master
        mainmenu = tk.Menu(root)
        root.config(menu=mainmenu)
        template_menu = tk.Menu(mainmenu, tearoff=0)
        # Выбор шаблона
        self.select_template()
        template_menu.add_command(label='Выбор шаблона', command=self.select_template)
        template_menu.add_command(label='Закачать вкладки из Chrome', command=self.get_tabs_from_chrome)
        mainmenu.add_cascade(label="Опции", menu=template_menu)
        # Конец меню
        self.tree = self.builder.get_object('Treeview_1')
        self.tree.column('#0', minwidth=100,width=200, stretch=tk.YES)
        self.logBox = builder.get_object('news_text_entry', master)

        self.yscrollbar = builder.get_object('Scrollbar_1', master)
        self.logBox['yscrollcommand'] = self.yscrollbar.set
        self.yscrollbar['command'] = self.logBox.yview

        self.yscrollbar2 = builder.get_object('Scrollbar_3', master)
        self.tree['yscrollcommand'] = self.yscrollbar2.set
        self.yscrollbar2['command'] = self.tree.yview

        warning_label = self.builder.get_object('warning_label')
        warning_label.config(foreground='red')
        self.warning_label = self.builder.get_object('warning_label')
        builder.connect_callbacks(self)


        self.url = self.builder.get_object('url_entry')

        self.url.bind("<FocusIn>", self.url_entry_Callback)
        self.url.event_add('<<Paste>>', '<Control-igrave>')
        self.url.event_add("<<Copy>>", "<Control-ntilde>")

        text_entry = self.builder.get_object('news_text_entry')
        self.text_entry = self.builder.get_object('news_text_entry')

        text_entry.event_add('<<Paste>>', '<Control-igrave>')
        text_entry.event_add("<<Copy>>", "<Control-ntilde>")

        self.date = self.builder.get_object('date_entry')

        self.date.event_add('<<Paste>>', '<Control-igrave>')
        self.date.event_add("<<Copy>>", "<Control-ntilde>")

        smi = self.builder.get_object('smi_entry')
        self.mass_media = self.builder.get_object('smi_entry')

        smi.event_add('<<Paste>>', '<Control-igrave>')
        smi.event_add("<<Copy>>", "<Control-ntilde>")

        self.title = self.builder.get_object('title_entry')

        self.tree.bind("<Button-1>", self.tree_one_click)

        self.paragraphs = []
        self.current_show_par = 0

        select = self.tree.focus()
        self.update_tree(select)
        self.tree.column('#0',width=355)

        START = False

    def change_section(self):
        inputDialog = DialogChangeSection(root)
        root.wait_window(inputDialog.top)
        selected_section = inputDialog.selected_section
        select = self.tree.selection()
        dbworker = DbWorker()
        for entry in select:
            id = self.tree.item(entry)['values'][0]
            dbworker.change_section(id,selected_section)
        self.update_tree(select=None)

    def select_template(self):
        global SELECTED_TEMPLATE
        global FULL_TEXT

        inputDialog = DialogSelectTemplate(root)
        root.wait_window(inputDialog.top)
        SELECTED_TEMPLATE = os.path.join(TEMPLATES_DIR, inputDialog.selected_template)
        database = SqliteDatabase(os.path.join(SELECTED_TEMPLATE, 'database.db'))
        database_proxy.initialize(database)

        config = configparser.ConfigParser()
        config.read(os.path.join(SELECTED_TEMPLATE,  'config.cfg'))
        FULL_TEXT = config.getboolean("Settings", "full_text")
        if not START:
            self.update_tree(select=None)

    def tree_one_click(self, event):
        triger_item = self.tree.identify('item', event.x, event.y)
        item = self.tree.item(triger_item)
        if len(item['values'])>0:
            id = item['values'][0]
        else:
            id = None
        if isinstance(id, int):
            dbworker = DbWorker()
            article = dbworker.get_article_by_id(id)
            self.show_article(article)
        else:
            self.clear_screen()

    def show_article(self, data):
        self.clear_screen()
        self.title.insert(tk.END, data['title'])
        self.date.insert(0, data['pubdate'])
        self.mass_media.insert(0, data['mass_media'])
        self.text_entry.insert(tk.END, data['text'])
        self.url.insert(0, data['url'])
        self.current_show_par = data['curr_show_p']
        е=1

    def id_up_trigger(self):
        select = self.tree.selection()[0]
        id = self.tree.item(select)['values'][0]
        dbworker = DbWorker()
        dbworker.update_id(id, 'up')
        self.update_tree(select={'values': [id]})

    def id_down_trigger(self):
        select = self.tree.selection()[0]
        id = self.tree.item(select)['values'][0]
        dbworker = DbWorker()
        dbworker.update_id(id, 'down')
        self.update_tree(select={'values': [id]})

    def delete_tree(self):
        select = self.tree.selection()[0]
        id = self.tree.item(select)['values'][0]
        if select:
            dbworker = DbWorker()
            dbworker.delete(int(id))
            # ToDo: возвращать select - предыдущий элемент
            self.update_tree(select=None)
            self.clear_screen()

    def update_in_bd(self):
        try:
            select = self.tree.selection()[0]
            id = self.tree.item(select)['values'][0]
        except:
            traceback.print_exc()
            logger.exception('Ошибка при получении записи из БД для обновления')
            id = ''
        if id:
            title = self.title.get(1.0, tk.END)
            date = self.date.get()
            mass_media = self.mass_media.get()
            text = self.text_entry.get(1.0, tk.END)
            url = self.url.get()
            try:
                dbworker = DbWorker()
                dbworker.update_row(id, url, title, date, mass_media, text,self.current_show_par)
                select = self.tree.selection()[0]
                self.update_tree(self.tree.item(select))
                self.warning_label.configure(text='Сохранено!')
            except:
                traceback.print_exc()
                self.warning_label.configure(text='Ошибка при сохранении')
                logger.exception('Ошибка при сохранении записи в БД')

    def update_tree(self, select):
        x = self.tree.get_children()
        for item in x: self.tree.delete(item)
        dbworker = DbWorker()
        sections = dbworker.get_sections()

        for section in sections:
            self.tree.insert('', 'end', text=section, values=(section,))

        for e in row.select().order_by(row.order_id.asc()):
            for child in self.tree.get_children():
                if self.tree.item(child)['values'][0] == e.section:
                    self.tree.insert(child, tk.END, text=e.title, values=(e.id,))
                self.tree.item(child, open=True)

                if select:
                    if self.tree.item(child)['values'][0] == select['values'][0]:
                        self.tree.selection_set(child)

                for item in self.tree.get_children(child):
                    if select:
                        if self.tree.item(item)['values'][0] == select['values'][0]:
                            self.tree.selection_set(item)

    def more_btn_press(self):
        currents_show_p = self.current_show_par
        if self.tree.selection():
            select = self.tree.selection()[0]
            id = self.tree.item(select)['values'][0]
            if isinstance(id, int):
                dbworker = DbWorker()
                data = dbworker.get_article_by_id(id)
                fulltext = data['fulltext']
                self.paragraphs = fulltext.split('\n')

        if currents_show_p == 0:
            end = 1
        else:
            end = currents_show_p + 1

        if not self.paragraphs[end]:
            end += 1

        if end == len(self.paragraphs):
            self.warning_label.configure(text='Достигнут конец статьи')
            return
        text = self.text_entry.get(1.0, tk.END)
        self.text_entry.delete(1.0, tk.END)

        text = text.rstrip() + ' ' + self.paragraphs[end]
        self.text_entry.insert(tk.END, text)
        self.current_show_par = end

    def get_date(self, date):

        month_list = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                      'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
        date_list = date.split('.')
        return (month_list[int(date_list[0]) - 1] + ' ' +
                date_list[1] + ' года')

    def clear_file(self):
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        header_template = self.template_dir + '\\main_doc_tmp.docx'
        new_main_doc_template = self.template_dir + '\\main_doc.docx'

        new_file = render_docx.RenderDocx(header_template)
        now_date = datetime.date.today()
        now_date2 = str(now_date.month) + '.' + str(now_date.year)
        datestr = self.get_date(now_date2)
        header_text = 'Обзор прессы за {0} {1} '.format((str(now_date.day)), datestr)
        context = {'header_text': header_text}
        if os.path.exists(new_main_doc_template):
            os.remove(new_main_doc_template)
        new_file.render(context)
        new_file.save(new_main_doc_template)

        try:
            os.remove(os.path.join(cur_dir, 'main_doc.docx'))
            src = os.path.join(self.template_dir, 'main_doc.docx')
            dst = os.path.join(cur_dir, 'main_doc.docx')
            copyfile(src, dst)
        except:
            traceback.print_exc()
            self.warning_label.configure(text='Ошибка при очистке файла')
            logger.exception('Ошибка при очистке файла')

    def attach(self, context=None):

        select = self.tree.selection()[0]
        section = self.tree.item(select)['values'][0]
        title = self.title.get(1.0, tk.END)
        date = self.date.get()
        mass_media = self.mass_media.get()
        text = self.text_entry.get(1.0, tk.END)
        url = self.url.get()

        dbwork = DbWorker()
        if isinstance(section, str):
            dbwork.insert(section, title, date, mass_media, text, url,self.fulltext,1)
            self.update_tree(self.tree.item(select))
            self.warning_label.configure(text='Вставлено')
            self.clear_screen()
        else:
            self.warning_label.configure(text='Вставка доступна только для раздела')

    def clear_screen(self):
        self.text_entry.delete(1.0, tk.END)
        self.date.delete(0, 'end')
        self.title.delete(1.0, tk.END)
        self.mass_media.delete(0, 'end')
        self.url.delete(0, 'end')

    def url_entry_Callback(self, event):
        entry1_ent = self.builder.get_object('url_entry')
        entry1_ent.selection_range(0, tk.END)

    def loading(self):
        label = self.builder.get_object('warning_label')
        if self.url.get() == '':
            label.configure(text='Укажите URL!')
        else:
            label.configure(text='Загружаю')
            # ToDo: Корректно обрабатывать вот такие URL - http://www.banki.ru/news/lenta/?id=10731264
            original_url = self.url.get()
            if self.url.get().find('?') > 0:
                url = self.url.get()[:self.url.get().find('?')]
            else:
                url = self.url.get()

            if original_url.find('banki.ru') > 0:
                url = original_url

            self.url.delete(0, tk.END)
            self.url.insert(0, url)
            root.update()
            try:
                self.parse_news()
            except:
                label.configure(text='Ошибка при обработке URL!')
                logger.exception('Ошибка при обработке URL! ( {0} )'.format(url))

    def alt_loading(self):
        label = self.builder.get_object('warning_label')
        if self.url.get() == '':
            label.configure(text='Укажите URL!')
        else:
            label.configure(text='Загружаю')
            if self.url.get().find('?') > 0:
                url = self.url.get()[:self.url.get().find('?')]
            else:
                url = self.url.get()
            self.url.delete(0, tk.END)
            self.url.insert(0, url)
            root.update()
            try:
                self.alt_parse_news()
            except:
                print('Ошибка при обработке URL!')
                traceback.print_exc()
                label.configure(text='Ошибка при обработке URL!')
                logger.exception('Ошибка при обработке URL! ( {0} )'.format(url))

    def parse_news(self):
        label = self.builder.get_object('warning_label')
        warning_label = self.builder.get_object('warning_label')
        url = self.url.get().strip()

        article = Myarticle(url)
        article.download()
        label.configure(text='Разбор')
        root.update()
        article.parse()
        article.postprocessing()

        if not FULL_TEXT:
            self.paragraphs = article.get_paragraphs()
            self.current_show_par = 0

        label.configure(text='')
        root.update()
        self.text_entry.configure(state='normal')  # enable insert
        self.text_entry.delete('1.0', tk.END)

        self.clear_screen()  # очистка экрана перед вставкой
        self.title.insert(tk.END, article.get_title())
        self.date.insert(0, article.get_pubdate())
        self.mass_media.insert(0, article.get_mass_media())
        self.text_entry.insert(tk.END, article.get_text())
        self.fulltext=article.get_full_text()
        self.url.insert(0, url)

        warning_label_text = ''
        if article.get_pubdate() == '':
            warning_label_text += 'Не найдена дата публикации! '

        if article.get_mass_media() == '':
            warning_label_text += 'Не найдено имени источника! '

        warning_label.configure(text=warning_label_text)

    def alt_parse_news(self):
        label = self.builder.get_object('warning_label')
        warning_label = self.builder.get_object('warning_label')
        url = self.url.get().strip()

        article = Myarticle(url)
        # article.download()
        label.configure(text='Разбор')
        root.update()
        # article.parse()
        #
        article.load_alt_engine()
        article.postprocessing(handle=False)

        if not FULL_TEXT:
            self.paragraphs = article.get_paragraphs()
            self.current_show_par = 0

        label.configure(text='')
        root.update()
        self.text_entry.configure(state='normal')  # enable insert
        self.text_entry.delete('1.0', tk.END)

        self.clear_screen()  # очистка экрана перед вставкой
        self.title.insert(tk.END, article.get_title())
        self.date.insert(0, article.get_pubdate())
        self.mass_media.insert(0, article.get_mass_media())
        self.text_entry.insert(tk.END, article.get_text())
        self.url.insert(0, url)

        warning_label_text = ''
        if article.get_pubdate() == '':
            warning_label_text += 'Не найдена дата публикации! '

        if article.get_mass_media() == '':
            warning_label_text += 'Не найдено имени источника! '

        warning_label.configure(text=warning_label_text)

    def insert_section(self, section=None):
        doc = render_docx.RenderDocx(self.template_dir + "\\section.docx")

        if section:
            insert_section = section
        else:
            insert_section = self.sections.get()

        context = {
            'section': insert_section
        }

        doc.render(context)
        doc.attach_to_main()
        doc.save('main_doc.docx')

    def create_file(self):

        self.template_dir = SELECTED_TEMPLATE

        self.clear_file()

        with open(os.path.join(SELECTED_TEMPLATE, 'sections.txt'), 'r') as myfile:
            data = myfile.read().split('\n')

        current_section = ''
        result = False
        for section in data:
            for e in row.select().where(row.section == section).order_by(row.order_id.asc()):
                # doc = render_docx.RenderDocx("templates\\news_template.docx")
                doc = render_docx.RenderDocx(self.template_dir + "\\news_template.docx")
                if current_section != e.section:
                    self.insert_section(e.section)
                    current_section = e.section

                context = {
                    'title': e.title,
                    'TITLE': e.title.upper(),
                    'title_link': 'url:' + e.title,
                    'pub_date': e.pubdate,
                    'url_link': e.url,
                    'news_text': e.text,
                    'listing_text': Listing(e.text),
                    'd': str(datetime.datetime.now().day),
                    'm': str(datetime.datetime.now().month),
                    'y': str(datetime.datetime.now().year),
                    'mass_media': e.mass_media
                            }
                try:
                    doc.render(context)
                    doc.attach_to_main()
                    doc.render_links(context)
                    doc.save('main_doc.docx')
                    result = True
                except:
                    result = False
                    traceback.print_exc()
                    logger.exception('Ошибка при вставке в файл: {0}'.format(str(context)))

        if result:
            self.warning_label.configure(text='Выгружено')
            showinfo('Результат выгрузки', 'Успешно выгрузили')
        else:
            self.warning_label.configure(text='Ошибка при вставке в файл. Он закрыт?')
            showerror('Результат выгрузки', 'Ошибка при выгрузки в файл. Проверьте, что он закрыт!')

    def open_project_folder(self):
        path = os.path.realpath(CURRENT_DIR)
        os.startfile(path)

    def get_tabs_from_chrome(self):

        select = self.tree.selection()
        if select:
            try:
                url_list = gettabs.get_tabs()
                for url in url_list:
                    self.clear_screen()
                    self.url.insert(0,url)
                    self.loading()
                    self.attach()
                showinfo('Успешно','Успешно загружено {0} вкладок'.format(len(url_list)))
            except:
                msg='Ошибка загрузки вкладок из chrome. Убедитесь, что Chrome запущен с ключом --remote-debugging-port=9222'
                showerror('Ошибка',msg)
                logging.exception(msg)
        else:
            showerror('Выберите раздел','Вы забыли выбрать раздел куда закачивать вкладки')

if __name__ == '__main__':
    root = tk.Tk()
    app = Application(root)
    root.mainloop()
