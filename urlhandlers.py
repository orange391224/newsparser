from bs4 import BeautifulSoup
from urllib.parse import urlsplit
import dateparser
import re

def dateextract(article, tag, dict_tags):
    try:
        soup = BeautifulSoup(article, 'lxml')
        datetag = soup.find(tag, dict_tags)
        date = dateparser.parse(datetag.text)
        pubdate = str(date.day) + '.' + str(date.month) + '.' + str(date.year)
        return pubdate
    except:
        return ''


def handle_by_url(myarticle):
    # url, article, title, publish_date
    url = myarticle.url
    article = myarticle.html
    news_title = myarticle.title
    publish_date = myarticle.publish_date
    news_text = myarticle.text
    pubdate = myarticle.publish_date
    izd_name = myarticle.mass_media
    news_title = myarticle.title

    clean_path = urlsplit(url)
    base_url = clean_path.netloc

    if base_url == 'www.bfm.ru':
        dict_tags = {'class': 'header__date'}
        pubdate = dateextract(article,'div',dict_tags)
        izd_name = 'BFM'

    if base_url == 'www.dairynews.ru':
        pubdate = article[article.find('"news-date-time">') + 17:article.find('"news-date-time">') + 27]
        izd_name = 'The Dairy News'
        soup = BeautifulSoup(article, "html.parser")
        img = soup.find('img', {'src': '/klever17.png'})
        if img:
            if img.find_previous_sibling():
                txt = img.find_previous_sibling().text
                if txt:
                    news_text = news_text[:news_text.find(txt.replace('\xa0', ' '))]

        txt = soup.find('div', {'class': 'page-text'})
        # news_text = txt.get_text(strip=True)
        news_text = txt.text
        news_text = news_text.replace('\t', '')
        news_text = news_text.replace('\r\n', '')
        news_text = news_text.replace('\r', '')
        news_text = news_text.replace('\n\n', '\n')
        txtlist = (repr(news_text)).split('\\n')
        text = []
        for line in txtlist:
            if len(line) < 3:
                pass
            else:
                text.append(line.lstrip())
        news_text = '\n'.join(text)
        lid = soup.find('div', {'class': 'page-preview'})
        if lid:
            news_text = lid.text.strip() + '\n' + news_text
        if news_text[len(news_text) - 1] == "'":
            news_text = news_text[:len(news_text) - 1]
        news_text = news_text.replace(u'\xa0', u' ').replace('\\xa0', '')

    if base_url == 'retailer.ru':
        izd_name = 'Ретейлер.ру'
        pubdate = str(publish_date.day) + '.' + str(publish_date.month) + '.' + str(publish_date.year)

        soup = BeautifulSoup(article)
        link = soup.find('em')
        if link:
            try:
                link_text = (link.text + link.next.next.text).replace('\xa0', ' ')
                news_text = news_text.replace(link_text, '').lstrip()
            except:
                pass

    if base_url == '1prime.ru':
        izd_name = 'Прайм'
        pubdate = str(publish_date.day) + '.' + str(publish_date.month) + '.' + str(publish_date.year)

        soup = BeautifulSoup(article, 'html.parser')
        lid = soup.find('div', {'class': 'article-body__content'})
        if lid:
            try:
                lid_text = lid.find('strong').text
            except:
                lid_text = lid.text
            lid_text = lid_text.replace('\xa0', ' ')
            news_text = news_text.replace(lid_text, '').lstrip()

    if base_url == 'realty.interfax.ru':
        full_date = article[
                    article.find('<p class="date">') + len('<p class="date">'):article.find(
                        '<p class="date">') + len(
                        '<p class="date">') + article[
                                              article.find('<p class="date">') + len('<p class="date">'):].find(
                        '</p>')]
        date = dateparser.parse(full_date[:full_date.find(',')])
        pubdate = str(date.day) + '.' + str(date.month) + '.' + str(date.year)
        izd_name = 'Интерфакс-недвижимость'

        news_text = news_text.replace(news_title, '')
        news_text = news_text[news_text.find('–', 0, 70) + 1:]
        news_text = news_text[news_text.find('—', 0, 70) + 1:]
        news_text = news_text[news_text.find('–', 0, 70) + 1:]
        news_text = news_text.lstrip()
        news_text = news_text.rstrip()

    if base_url == 'www.rbc.ru':
        try:
            publish_date = re.findall(r'/(\d{1,2})/(\d{1,2})/(\d{4})/', url)
            pubdate = '{0}.{1}.{2}'.format(publish_date[0][0], publish_date[0][1], publish_date[0][2])
        except:
            pubdate = ''
        izd_name = 'РБК'

    if base_url == 'iz.ru':
        pubdate = str(publish_date.day) + '.' + str(publish_date.month) + '.' + str(publish_date.year)
        izd_name = 'Известия'

    if base_url == 'www.kommersant.ru':
        soup = BeautifulSoup(article, 'html.parser')
        a = soup.find('p', {'class': 'b-article__text document_authors'})
        if a:
            news_text = news_text.replace(a.text, '')

        pubdate = str(publish_date.day) + '.' + str(publish_date.month) + '.' + str(publish_date.year)
        izd_name = 'Коммерсант'
        title_search = soup.find('h2',{'class':'article_name'})
        if title_search:
            news_title = title_search.text
            news_text = news_text.replace(title_search.text,'')
        subheader_search = soup.find('h1', {'class':'article_subheader'})
        if subheader_search:
            news_text = news_text.replace(subheader_search.text,'').lstrip()

    if base_url == 'vm.ru':
        dict_tags = {'class': 'date'}
        pubdate = dateextract(article, 'div', dict_tags)
        izd_name = 'Вечерняя Москва'

    if base_url == 'www.interfax.ru':
        pubdate = str(publish_date.day) + '.' + str(publish_date.month) + '.' + str(publish_date.year)
        izd_name = 'Интерфакс'
        if news_text.find('INTERFAX.RU', 0, 40):
            news_text = news_text[news_text.find('INTERFAX.RU', 0, 40) + len('INTERFAX.RU') + 3:]

    if base_url == 'realty.ria.ru':
        pubdate = str(publish_date.day) + '.' + str(publish_date.month) + '.' + str(publish_date.year)
        izd_name = 'РИА Новости'
        news_text = news_text.replace(news_title, '').lstrip()
        soup = BeautifulSoup(article, 'html.parser')
        lid = soup.find('div', itemprop='articleBody')
        if lid:
            lid_text = lid.find('strong').text.replace('\xa0', ' ')
            news_text = news_text.replace(lid_text, '').lstrip()

    if base_url == 'ria.ru':
        pubdate = str(publish_date.day) + '.' + str(publish_date.month) + '.' + str(publish_date.year)
        izd_name = 'РИА Новости'
        soup = BeautifulSoup(article, 'lxml')
        lid = soup.find('strong')
        news_text = news_text.replace(news_title + '\n\n', '')
        news_text = news_text.replace(lid.text.replace(u'\xa0', u' '), '').lstrip()
        #удаление тэга alt
        for image in soup.findAll("img"):
            text_alt = image.get('alt', '')
            news_text = news_text.replace(text_alt, '').lstrip()

        i = 0
        for symbol in news_text:
            if i < 3:
                if symbol == '.':
                    news_text = news_text.replace('.', '', 1)
                else:
                    break
                i = i + 1

        news_text = news_text.lstrip()

    if base_url == 'www.vedomosti.ru':
        pubdate = str(publish_date.day) + '.' + str(publish_date.month) + '.' + str(publish_date.year)
        izd_name = 'Ведомости'
        soup = BeautifulSoup(article, 'html.parser')
        news_title = soup.find('title').text
        news_title = news_title.replace('– ВЕДОМОСТИ','')

    if base_url == 'ruskline.ru':
        soup = BeautifulSoup(article, "lxml")
        a = soup.findAll('p', {'align': 'right'})
        if a:
            try:
                deletestr = a[0].next.next + a[0].next.nextSibling
                deletestr = re.sub(' +', ' ', deletestr)
                news_text = news_text.replace(deletestr, '')
                date = dateparser.parse(a[0].next.nextSibling)
                pubdate = str(date.day) + '.' + str(date.month) + '.' + str(date.year)
            except:
                print('Исключение в обработке ruskline.ru')
        news_text = re.sub(r'\n+', '\n', news_text).strip()
        izd_name = 'Русская народная линия'

    if base_url == 'tass.ru':
        dict_tags = {"class": "b-material__date"}
        #pubdate = dateextract(article, "span", dict_tags)
        izd_name = 'ТАСС'

        soup = BeautifulSoup(article, 'html.parser')
        txt_list = []
        for txt in soup.findAll('div', {'class':'text-block'}):
            txt_list.append(txt.text)
        news_text = ''.join(txt_list).lstrip()
        f = re.match('(.*?)ТАСС.*?\\.',news_text)
        news_text = news_text.replace(f.group(0), '').lstrip()

    if base_url == 'realty.rbc.ru':
        pubdate = dateextract(article, 'span', {'class': 'article__header__date'})
        izd_name = 'РБК-Недвижимость'

        soup = BeautifulSoup(article, 'lxml')
        foto_tags = soup.findAll('span', {'class': 'article__main-image__author'})
        for tag in foto_tags:
            news_text = news_text.replace(tag.text.strip(), '')

    if base_url == 'www.energyland.info':
        soup = BeautifulSoup(article, 'lxml')
        rubric = soup.find('div', {'class': 'span'})
        news_text = news_text.replace(rubric.text, '').lstrip()
        plashka = soup.find('div', {'class': 'plashka'})
        news_text = news_text.replace(plashka.find_next_sibling("b").next_sibling, '').lstrip()
        news_text = news_text.replace('\n\n', '\n')
        allnews = soup.find('span', {'class': 'grey_title'})
        news_text = news_text.replace(allnews.text, '')
        try:
            date = dateparser.parse(plashka.find_next_sibling("b").next_sibling)
            pubdate = str(date.day) + '.' + str(date.month) + '.' + str(date.year)
        except:
            pass
        izd_name = 'Energyland.info'


    #Если для сайта нет обработки
    if izd_name == '':
        izd_name = base_url.replace('www.','')
        if not pubdate:
            pubdate = ''




    return_dict = {'izd_name': izd_name, 'pubdate': pubdate, 'news_text': news_text, 'news_title' : news_title}

    return return_dict
