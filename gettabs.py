from chromote import Chromote
from urllib.parse import urlsplit

def get_tabs():
    urls = []
    exclude_list = ['br-analytics.ru',
                    'docs.google.com',
                    'mail.google.com',
                    'vk.com',
                    'www.loveradio.ru'
                    ]

    tabs = Chromote(host="localhost", port=9222)
    for tab in tabs:
        clean_path = urlsplit(tab.url)
        base_url = clean_path.netloc
        if base_url not in exclude_list:
            urls.append(tab.url)
    return urls
