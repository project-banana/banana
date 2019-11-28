from bs4 import BeautifulSoup
from banana import connection
import sqlite3, sys
from constants import *

def create_database():
    conn = sqlite3.connect(database_file)
    cursor = conn.cursor()
    query_create_table = 'CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY, text_id TEXT, href TEXT, title TEXT, data_url TEXT, poster_url TEXT, quality TEXT);'
    cursor.execute(query_create_table)
    connection.session_destroy()
    session = connection.session_init()
    idx = 1
    done = False
    while not done:
        page_url='https://solarmoviez.ru/movie/filter/movies/latest/all/all/all/all/all/page-%d.html' % (idx)
        req = session.get(page_url)
        if req.status_code != 200:
            conn.close()
            sys.exit('error: status code, %d' % (req.status_code))
        soup = BeautifulSoup(req.content.decode('utf-8'), 'html.parser')
        idx += 1
        items = soup.find_all('div', class_='ml-item')
        if len(items) == 0:
            done = True
            break
        for item in items:
            href = item.a['href']
            title = item.a['title']
            data_url = item.a['data-url']
            poster_url = item.img['data-original']
            quality = ''
            if item.span['class'] == ['mli-quality']:
                quality = item.span.text
            text_id = data_url.split('.html')[0].split('/')[-1]
            id_ = int(text_id)
            cursor.execute('INSERT INTO movies VALUES (?,?,?,?,?,?,?)', (id_, text_id, href, title, data_url, poster_url, quality))
        conn.commit()
    conn.close()
