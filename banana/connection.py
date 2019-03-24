import os
import time
import pickle
import socket
import requests
from selenium import webdriver

user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.75 Safari/537.36'
get_cookies_url = 'https://solarmoviez.ru/movie/filter/movies.html'
cookies_file = 'cookies.pkl'
session_file = 'session.pkl'
#chrome_binary = '/opt/google/chrome/chrome'
chrome_binary = '/tmp/Google Chrome.app/Contents/MacOS/Google Chrome'
cloudflare_sleep_delay = 10
chrome_args = [
        '--start-maximized',
        '--start-fullscreen',
        '--headless',
        '--window-size=800x1200'
        ]

def is_online(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except:
        return False

def get_cookies(url=get_cookies_url):
    def is_valid_cookie(cookies_file=cookies_file, cookie_name='cf_clearnace'):
        try:
            with open(cookies_file, 'rb') as fp:
                data = pickle.load(fp)
                fp.close()
            for cookie in data:
                if cookie['name'] == cookie_name:
                    if cookie['expiry'] > time.time() + 60:
                        return True
                    break
        except:
            return False

    if is_valid_cookie():
        return

    options = webdriver.ChromeOptions()
    options.binary_location = chrome_binary
    for arg in chrome_args:
        options.add_argument(arg)
    options.add_argument(f'user-agent={user_agent}')        
    driver = webdriver.Chrome(options=options)
    driver.get(get_cookies_url)
    time.sleep(cloudflare_sleep_delay)
    cookies = driver.get_cookies()
    driver.quit()        
    with open(cookies_file, 'wb') as fp:
        pickle.dump(cookies, fp)
        fp.close()

def session_init():
    def session_create():
        get_cookies()
        with open(cookies_file, 'rb') as fp:
            cookies = pickle.load(fp)
            fp.close()
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        session.headers.update({'User-Agent': user_agent})
        with open(session_file, 'wb') as fp:
            pickle.dump(session, fp)
            fp.close()
        return session
    def session_load():
        try:
            with open(session_file, 'rb') as fp:
                session = pickle.load(fp)
                fp.close()
                return session
        except:
            return None
            
    session = session_load()
    if not session:
        session = session_create()
    return session

def session_destroy():
    if os.path.exists(cookies_file):
        os.unlink(cookies_file)
    if os.path.exists(session_file):        
        os.unlink(session_file)
