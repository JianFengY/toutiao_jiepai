"""
Created on 2018/2/27
@Author: Jeff Yang
"""
import re
import requests
from urllib.parse import urlencode  # 把字典变成URL参数
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
import json
import pymongo
from hashlib import md5
import os
from multiprocessing import Pool

from jiepai_spider.config import *

client = pymongo.MongoClient(MONGO_URL, connect=False)
db = client[MONGO_DB]


def get_page_index(offset, keyword):
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': '20',
        'cur_tab': '3',
        'from': 'gallery',
    }
    url = "https://www.toutiao.com/search_content/?" + urlencode(data)
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print("请求索引页出错")
        return None


def parse_page_index(html):
    data = json.loads(html)
    if data and 'data' in data.keys():
        for item in data.get('data'):
            yield item.get('article_url')


def get_page_detail(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print("请求详情页出错", url)
        return None


def parse_page_detail(html, url):
    soup = BeautifulSoup(html, 'lxml')
    title = soup.select('title')[0].get_text()
    print(title)
    image_pattern = re.compile('gallery: JSON.parse\("(.*?)"\),', re.S)
    result = re.search(image_pattern, html)
    if result:
        # print(bytes(result.group(1),encoding='utf-8').decode('unicode_escape'))
        result_json = re.sub('\\\/', '/', bytes(result.group(1), encoding='utf-8').decode('unicode_escape'))
        data = json.loads(result_json)
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            images = [item.get('url') for item in sub_images]
            for image in images:
                download_image(image)
            return {
                'title': title,
                'url': url,
                'image': images,
            }


def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print("存储到MongoDB成功", result)
        return True
    return False


def download_image(url):
    print("正在下载：", url)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            save_image(response.content)  # content返回二进制内容
        return None
    except RequestException:
        print("请求图片出错", url)
        return None


def save_image(content):
    file_path = '{0}/images/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()


def main(offset):
    html = get_page_index(offset, KEYWORD)
    for url in parse_page_index(html):
        html = get_page_detail(url)
        if html:
            result = parse_page_detail(html, url)
            if result:
                save_to_mongo(result)


if __name__ == '__main__':
    groups = [x * 20 for x in range(GROUP_START, GROUP_END + 1)]
    pool = Pool()
    pool.map(main, groups)
