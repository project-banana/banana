#!/usr/bin/env python3
from bs4 import BeautifulSoup
from banana import connection
from slack import WebClient
from credentials import *
from constants import *
import sqlite3, sys

def is_new_record(conn, text_id):
    ret = conn.execute('SELECT 1 FROM movies WHERE id=?', (text_id,))
    result = ret.fetchone()
    if result and result[0]:
        return False
    return True

def update_database():
    conn = sqlite3.connect(database_file)
    cursor = conn.cursor()
    query_create_table = 'CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY, text_id TEXT, href TEXT, title TEXT, data_url TEXT, poster_url TEXT, quality TEXT);'
    cursor.execute(query_create_table)
    connection.session_destroy()
    session = connection.session_init()
    idx = 1
    done = False
    new_records = []
    while not done:
        page_url = solar_domain + '/movie/filter/movies/latest/all/all/all/all/all/page-%d.html' % (idx)
        req = session.get(page_url)
        if req.status_code != 200:
            conn.close()
            sys.exit('error: status code, %d' % (req.status_code))
        soup = BeautifulSoup(req.content.decode('utf-8'), 'html.parser')
        idx += 1
        items = soup.find_all('div', class_='ml-item')
        new_on_this_page = 0
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
            if not is_new_record(conn, text_id):
                continue
            new_on_this_page += 1
            record = {'href': href, 'title': title, 'data_url': data_url, 'poster_url': poster_url, 'quality': quality, 'text_id': text_id}
            new_records.append(record)
            cursor.execute('INSERT INTO movies VALUES (?,?,?,?,?,?,?)', (id_, text_id, href, title, data_url, poster_url, quality))
        conn.commit()
        if new_on_this_page == 0:
            break
    conn.close()
    return new_records

def slack_update(new_records):
    if len(new_records) < 1:
        return
    sc = WebClient(token=SLACK_TOKEN)
    res = sc.chat_postMessage(channel=MY_CHANNEL, text='*database updated!!*')
    if not res['ok']:
        return
    for rec in new_records:
        msg = '`%s` *%s* %s' % (rec['text_id'], rec['title'], rec['poster_url'])
        if len(rec['quality']) > 0:
            msg = '`%s` *%s* _%s_ %s' % (rec['text_id'], rec['title'], rec['quality'], rec['poster_url'])
        sc.chat_postMessage(channel=MY_CHANNEL, text=msg, thread_ts=res['ts'])

if __name__ == '__main__':
    if not connection.is_online():
        sys.exit('offline')
    slack_update(update_database())
