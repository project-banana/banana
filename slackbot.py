#!/usr/bin/env python3
import time
import sqlite3
import subprocess
from slackclient import SlackClient
import requests
import re
import json
from banana import get_link, connection
from credentials import *
from constants import *

# credentials.py
#   my_channel  = 'xxxxxxxxx'
#   my_user     = 'xxxxxxxxx'
#   slack_token = 'xxxx-xxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

def db_title_from_id(text_id):
    conn = sqlite3.connect(database_file)
    ret = conn.execute('SELECT title FROM movies WHERE id=?', (text_id,))
    result = ret.fetchone()
    conn.close()
    if result and result[0]:
        return result[0]
    else:
        return None

def imdb_title(title):
    title=title.lower();                                #to lowercase
    title=re.sub("[^a-z\d\s]", "", title);              #strip all except alnum and spaces
    title=" ".join(title.split())                       #trim extra spaces
    search=re.sub("[\s]", "_", title);                  #replace spaces with underscores
    if len(search) < 1:                                 #format https://v2.sg.media-imdb.com/suggests/n/no_country_for_old_men.json
        return 'bad search string'
    request_url = 'https://v2.sg.media-imdb.com/suggests/' + search[0:1] + '/' + search + '.json'
    req = requests.get(request_url);
    if req.status_code != 200:
        return 'imdb look-up failed, response status code: %d' % (req.status_code,)
    json_str = req.content.decode('utf-8');             #transform from bytes t text
    arr = json.loads(json_str[json_str.find("{"):-1])   #json decode
    if ('d' in arr) and ('id' in arr['d'][0]):
        imdb_id = arr['d'][0]['id']
        if imdb_id[0] == 't' and imdb_id[1] == 't':
            return 'https://www.imdb.com/title/' + imdb_id + '/';
    return 'nothing found, sry :cry:'

def imdb_search(args):
    if len(args) < 1:
        return 'syntax is: `!imdb` *title*  or `!imdb` *id*'
    search = None
    if len(args) == 1 and args[0].isdigit():                                #numeric
        search = db_title_from_id(args[0])
    if not search:
        search = ' '.join(args)
    return imdb_title(search)

def link(args):
    if len(args) < 1:
        return 'syntax is: `!link` *id*';
    if args[0].isdigit() == False:
        return 'must be a numeric id';
    success, data = get_link.get_link(args[0])
    if not success:
        return 'forgive me senpai, i failed :disappointed:'
    result = ''
    for item in data:
        result += '*%s*\n%s\n' % (item['title'], item['link'])
        if 'subs' in item:
            result += '```%s```\n' %(item['subs'],)
    return result

def poster(args):
    if len(args) < 1:
        return 'syntax is: `!poster` *id*';
    if args[0].isdigit() == False:
        return 'must be a numeric id';
    conn = sqlite3.connect(database_file)
    ret = conn.execute('SELECT id, title, poster_url FROM movies WHERE id=?;', (args[0],))
    result = ret.fetchone()
    conn.close()
    if result:
            return '`%s` *%s* %s\n' % (result[0], result[1], result[2])
    return 'no matches found :slightly_frowning_face:'

def find(args):
    if len(args) < 1:
        return 'syntax is: `!find` *title*'
    conn = sqlite3.connect(database_file)
    ret = conn.execute("SELECT id, title, quality FROM movies WHERE title LIKE ?;", ('%' + '%'.join(args) + '%',))
    result = ret.fetchall()
    conn.close()
    response='found ' + str(len(result)) + ' matches\n'
    for movie in result:
        if len(movie[2]) > 0:
            response += '`%s` *%s* _%s_\n' % (movie[0], movie[1], movie[2])
        else:
            response += '`%s` *%s*\n' % (movie[0], movie[1])
    return response

def info(args):
    return 'available commands are:\n`!poster` *id*\n`!link` *id*\n`!find` *title*\n`!imdb` *title* or *id*\n'

#########################################################################

bot_commands = {'!find': find, '!link': link, '!info': info, '!poster': poster, '!imdb': imdb_search}
while True:
    def log_message(msg):
        with open('banana.log', 'a+') as fp:
            s = '%s %s\n' % (time.strftime("%Y/%m/%d %H:%M:%S", time.localtime()), msg)
            print(s)
            fp.write(s)
            fp.close()

    def is_message(m):
        if 'type' not in m:             return False
        if m['type'] != 'message':      return False
        if 'channel' not in m:          return False
        if m['channel'] != my_channel:  return False
        if 'user' not in m:             return False
        if m['user'] == my_user:        return False
        if 'text' not in m:             return False
        return True

    if not connection.is_online():
        time.sleep(1)
        continue
    sc = SlackClient(slack_token)
    if not sc.rtm_connect(with_team_state=False):
        time.sleep(1)
        continue
    log_message('online')
    while True:
        try:
            for m in sc.rtm_read():
                if not is_message(m):
                    time.sleep(1)
                    continue
                args = m['text'].split()
                if args[0] not in bot_commands:
                    continue
                thread_ts = None
                if 'thread_ts' in m:
                    thread_ts = m['thread_ts']
                else:
                    thread_ts = m['ts']
                func = bot_commands[args[0]]
                sc.rtm_send_message(my_channel, '<@'+m['user']+'>, ' + func(args[1:]), thread_ts)
            time.sleep(1)
        except:
            break
    log_message('offline')
