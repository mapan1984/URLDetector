#!/usr/bin/python3

'''
1. 递归检测所有sohu.com域名（包含子域名）的页面以及这些页面上的链接的可达性。
2. 对于错误的链接记录到日志中，日志包括：URL，时间，错误状态。
'''

import re
import queue
import socket
import datetime
import threading
from urllib.error import URLError, HTTPError
from urllib.request import urlopen, urljoin, Request

# timeout in seconds
socket.setdefaulttimeout(10)

# 线程数量
THREAD_NUM = 4

# 以记录的链接集合
CRAWLED_URLS = set()

# URL队列
URLS_Q = queue.Queue()

# 提取链接
HREF_PAT = re.compile(r'(?<=href=\").*?(?=\")')

HEADERS = {
    'Connection':'keep-alive',
    'Referer':'http://www.sohu.com',
    'Accept-Language':'zh-CN,zh;q=0.8,en;q=0.6',
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36'
}

class Logging:
    """一个异步进行记录的类
    实例为可以进行调用的记录函数
    """

    def __init__(self, logfile):
        self.logfile = open(logfile, 'a')
        self.lock = threading.Lock()

    def __del__(self):
        self.logfile.close()

    def __log(self, url, error):
        date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log = " - ".join([url, error, date]) + '\n'
        # print(log)
        with self.lock:
            self.logfile.write(log)

    def __call__(self, url, error):
        thr = threading.Thread(target=self.__log, args=[url, error])
        thr.start()
        return thr

log = Logging('url_error.log')


class Crawler(threading.Thread):

    def __init__(self, queue):
        super(Crawler, self).__init__()
        self._queue = queue

    def open_url(self, url):
        """发送请求，如果链接可得，返回响应；否则记录错误信息"""
        request = Request(url, headers=HEADERS)
        try:
            response = urlopen(request)
        except HTTPError as error:
            log(url, str(error.reason))
        except URLError as error:
            log(url, str(error.reason))
        except:
            log(url, 'Unkown Error')
        else:
            print("{:>10}{:>10}"\
                    .format(URLS_Q.qsize(), len(CRAWLED_URLS)), end='\r')
            return response


    def add_links(self, response):
        """将响应中的链接解析出来，加入self._queue"""

        # 只解析html中的链接
        if response.headers.get('Content-Type').split(';')[0] != 'text/html':
            return

        hrefs = HREF_PAT.finditer(str(response.read()))

        for href in hrefs:
            new_url = urljoin(response.geturl(), href.group())
            if 'sohu.com' not in new_url:  # 不在范围
                continue
            if new_url[0:4] != 'http':  # 去除mailto和Bookmarklet
                continue
            new_url = new_url.split('#')[0]  # 去掉位置参数部分
            if new_url not in CRAWLED_URLS:
                CRAWLED_URLS.add(new_url)
                self._queue.put(new_url)

    def run(self):
        while self._queue.qsize() > 0:
            url = self._queue.get()

            response = self.open_url(url)
            if response is None:
                continue

            self.add_links(response)

            self._queue.task_done()


if __name__ == '__main__':
    URLS_Q.put('http://www.sohu.com')

    threads = []
    for i in range(THREAD_NUM):
        c = Crawler(URLS_Q)
        c.start()
        threads.append(c)
    for t in threads:
        t.join()

