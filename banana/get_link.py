#!/usr/bin/env python3
import sys
import json
from banana import connection
import requests
from bs4 import BeautifulSoup
from constants import *

debug = False
ajax_movie_episodes = solar_domain + '/ajax/v4_movie_episodes/'
ajax_movie_embed = solar_domain + '/ajax/movie_embed/'

#------------------------------------------------------------------------------
def streamango_encode_url(plain, key):
    def try_ord(s, i):
        result = 0
        try: result = ord(s[i])
        except: pass
        return result

    reverse_base = '=/+9876543210zyxwvutsrqponmlkjihgfedcbaZYXWVUTSRQPONMLKJIHGFEDCBA'
    i = 0
    result = ''
    while i < len(plain):
        a = reverse_base[(try_ord(plain, i) ^ key) >> 2]
        b = reverse_base[(((try_ord(plain, i) ^ key) << 4) & 63) + (try_ord(plain, i + 1) >> 4)]; i += 1
        c = reverse_base[((try_ord(plain, i) & 15) << 2) + (try_ord(plain, i + 1) >> 6)]; i += 1
        d = reverse_base[try_ord(plain, i) & 63]; i += 1
        if i - 2 == len(plain):
            c = reverse_base[64]; d = reverse_base[64]
        elif i - 1 == len(plain):
            d = reverse_base[64]
        result += a + b + c + d
    return result

#------------------------------------------------------------------------------
def streamango_decode_url(encoded, key):
    reverse_base = '=/+9876543210zyxwvutsrqponmlkjihgfedcbaZYXWVUTSRQPONMLKJIHGFEDCBA'
    i = 0
    result = ''
    while i < len(encoded):
        a = reverse_base.find(encoded[i]); i+=1
        b = reverse_base.find(encoded[i]); i+=1
        c = reverse_base.find(encoded[i]); i+=1
        d = reverse_base.find(encoded[i]); i+=1

        x = (a << 2) | (b >> 4)
        y = ((b & 15) << 4) | (c >> 2)
        z = ((c & 3) << 6) | d

        result += chr(x ^ key)

        if y != 63:
            result += chr(y)
        if z != 64:
            result += chr(z)
    return result

#------------------------------------------------------------------------------
def get_streamango_link(session, sm_url):
    sm_starts = 'https://streamango.com/embed/'
    if not sm_url.startswith(sm_starts):
        return False, None
    sm_req = session.get(sm_url)
    if sm_req.status_code != 200:
        if debug:
            print('get_streamango_link() failed, status code: ', sm_req.status_code)
        return False, None
    sm_html = sm_req.content.decode('utf-8')
    sm_soup = BeautifulSoup(sm_html, features='html.parser')
    meta_name = sm_soup.find('meta', {'name':'og:title'})
    if not meta_name:
        if debug:
            print('get_streamango_link() failed, could find meta og:title, file was removed?')
        return False, None
    og_title = meta_name['content']
    enc0 = sm_html[sm_html.find('srces.push( {'):]
    enc1 = enc0[enc0.find("d('") + 1:]
    enc2 = enc1[:enc1.find(')') + 1]
    if (enc2[0] != '(') or (enc2[-1] != ')'):
        if debug:
            print('get_streamango_link() failed, could not find encoded url pattern')
        return False, None
    enc_temp = '[' + enc2[1:-1].replace('\'','"') + ']' #replace ('x') with ["x"]
    sm_json = json.loads(enc_temp)
    result = streamango_decode_url(sm_json[0], sm_json[1])
    if result[0:2] == '//':
        result = 'https:' + result
    if debug:
        print(og_title, result)
    return True, {'title':og_title, 'link':result} #FIXME: add subtitle url to result

#------------------------------------------------------------------------------
def get_vidcloud_link(session, url):
    domains = ['https://vcstream.to', 'https://loadvid.online', 'https://vidcloud.co']
    base = None
    for d in domains:
        if url.startswith(d + '/embed/'):
            base = d
            break
    if not base:
        return False, None
    starts = base + '/embed/'

    fid = url[len(starts):]
    if '/' in fid:
        fid = fid[:fid.find('/')]
    if (not fid) or (len(fid) < 1):
        if debug:
            print('get_vidcloud_link() failed, no file id')
        return False, None
    vc_url = base + '/player?fid=' + fid + '&page=embed'
    vc_req = session.get(vc_url)
    if vc_req.status_code != 200:
        if debug:
            print('get_vidcloud_link() failed, status code: ', vc_req.status_code)
        return False, None
    vc_json = json.loads(vc_req.content.decode('utf-8'))
    if vc_json['status'] != True:
        if debug:
            print('get_vidcloud_link() failed, response json status: ', vc_json['status'])
        return False, None
    vc_html = vc_json['html']
    title = vc_html[vc_html.find("title: '") + 8:]
    title = title[:title.find("'")]
    if debug:
        print(title)
    file_json = vc_html[vc_html.find('sources = [{"file":"') + 11:]
    file_json = file_json[:file_json.find('"}') + 2]
    try:
        result = json.loads(file_json)
    except:
        if debug: print('get_vidcloud_link() failed, couldnt parse javascript')
        return False, None
    filelink = result['file']
    if debug:
        print('vidcloud url', filelink)
    tracks = vc_html[vc_html.find('tracks = [{"file"') + 9:]
    tracks = tracks[:tracks.find('}]') + 2]
    result = None
    try:
        track = json.loads(tracks)
        result = track[0]['file']
        if debug:
            print('track', result)
    except:
        pass
    data = {'title':title, 'link': filelink}
    if result:
        data['subs'] = result
    return True, data

#------------------------------------------------------------------------------
def pick_preferred_mirror(episode, servers, mirror_name): #episode is a list[], servers is a dict{}
    for mirror in episode:                              # function returns index of mirror in episode[], or none
        srv_id = mirror['server']
        if servers[srv_id] == mirror_name:
            return episode.index(mirror)
    return None

###############################################################################
#--[step 1]--------------------------------------------------------------------

def get_episode(session, episode):
    url2 = ajax_movie_embed + episode['id']
    req2 = session.get(url2)
    if req2.status_code != 200: #maybe try other episode id's ?
        if debug:
            print('failed at step 2a: ', ajax_movie_embed, 'response code: ', req2.status_code)
        return False, None
    json2 = json.loads(req2.content.decode('utf-8'))
    if json2['status'] != 1:
        if debug:
            print('failed at step 2b: ', ajax_movie_embed, 'response json status: ', json2['status'])
            print(json2)
        return False, None
    url3 = json2['src']
    if url3.startswith('https://vcstream.to/embed/'):
        return get_vidcloud_link(session, url3)
    elif url3.startswith('https://loadvid.online/embed/'):
        return get_vidcloud_link(session, url3);
    elif url3.startswith('https://vidcloud.co/embed/'):
        return get_vidcloud_link(session, url3);
    elif url3.startswith('https://streamango.com/embed/'):
        return get_streamango_link(session, url3)
    else:
        if debug:
            print("i don't know how to process this: ", url3)
        return False, None

def get_link(movie_id, retry_cloudflare=True):
    if not movie_id.isdigit():
        if debug:
            print('id must be numeric')
        return False, None
    session = connection.session_init()
    url1 = ajax_movie_episodes + movie_id
    req1 = session.get(url1)
    if debug: print(url1)
    if req1.status_code == 503 and retry_cloudflare == True:        #cloudflare
        connection.session_destroy()                                #
        get_link(movie_id, False)                                   #if 503, remove session and cookies and retry
    if req1.status_code != 200:
        if debug:
            print('failed at step 1a: ', ajax_movie_episodes, 'response code: ', req1.status_code)
        return False, None
    json1 = json.loads(req1.content.decode('utf-8'))
    if debug: print('STEP 1-A', json1)
    if not json1['status']:
        if debug:
            print('failed at step 1b: ', ajax_movie_episodes, 'response json status: ', json1['status'])
        return False, None
    html1 = json1['html']
    soup1 = BeautifulSoup(html1, features='html.parser')
    servers = {}
    for li in soup1.find_all('li', {'class': 'server-item embed'}):
        _id = li['data-id']
        _name = li.text.strip()
        servers[_id] = _name
    episodes = {}
    for li in soup1.find_all('li', {'class': 'ep-item'}):
        index = li['data-index']
        if index not in episodes:
            episodes[index] = []
        ep = {}
        ep['id'] = li['data-id']
        ep['server'] = li['data-server']
        ep['text'] = li.text.strip()
        episodes[index].append(ep)

#--[step 2]--------------------------------------------------------------------
    if debug:
        print('STEP 2', servers, episodes)

    result = []
    for ep in episodes:
        idx = pick_preferred_mirror(episodes[ep], servers, 'VidCloud')          # preferred
        if idx:
            success, data = get_episode(session, episodes[ep][idx])
            if success:
                result.append(data)
                continue    #go to parent loop, take next episode
            else:
                episodes[ep].pop(idx)   #remove so we don't try it again

        mirrors = episodes[ep]
        for mirror in mirrors:
            success, data = get_episode(session, mirror)
            if success:
                result.append(data)
                break   # break out of mirrors loop because we have a valid link
    if len(result) > 0:
        return True, result
    else:
        return False, None

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('give me a solarmoviez id')
    success, data = get_link(sys.argv[1])
    if debug: print('success:', success)
    if success:
        for item in data:
            print(item)
