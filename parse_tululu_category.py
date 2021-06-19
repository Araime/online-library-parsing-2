import argparse
import json
import logging
import os
from pathvalidate import sanitize_filename
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import requests
from tqdm import tqdm


def get_books_urls(genre_url, page):
    first_page = 'https://tululu.org/l55/1'
    response = requests.get(first_page)
    soup = BeautifulSoup(response.text, 'lxml')
    end_page_number = int(soup.find_all(class_='npage')[-1].text)

    if page > end_page_number:
        raise ValueError(f'Страницы под номером {page} не существует')
    url = f'{genre_url}{page}'
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    books = soup.find_all('table', class_='d_book')
    books_ids = [book.a['href'] for book in books]
    books_links = [urljoin('https://tululu.org', book_id) for book_id in books_ids]
    return books_links


def get_book_link(book_id):
    url = f'https://tululu.org/txt.php'
    payload = {'id': book_id}
    response = requests.get(url, params=payload)
    check_for_redirect(response)
    return response.url


def check_for_redirect(response):
    if response.history:
        raise requests.HTTPError(response.history)


def parse_book_page(book_id, books_folder, images_folder):
    book_page_link = f'https://tululu.org/b{book_id}'
    response = requests.get(book_page_link)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    title_tag = soup.find('h1')
    title = title_tag.text.split('::')
    book_name = sanitize_filename(title[0].strip())
    author = title[1].strip()
    img = soup.find(class_='bookimage').find('img')['src']
    filename = img.split('/')[-1]
    img_src = os.path.join(images_folder, filename)
    book_path = os.path.join(books_folder, f'{book_name}.txt')
    image_link = urljoin('https://tululu.org', img)
    comments_tags = soup.find_all('div', class_='texts')
    comments = [comment.span.text for comment in comments_tags]
    genre_tag = soup.find('span', class_='d_book').find_all('a')
    genres = [genre.text for genre in genre_tag]
    book_page_information = {
        'book_name': book_name,
        'author': author,
        'img_path': img_src,
        'book_path': book_path,
        'comments': comments,
        'genre': genres
    }
    return book_page_information, image_link


def create_books_description(description, folder):
    json_path = os.path.join(folder, 'books_description.json')
    with open(json_path, 'w', encoding='utf-8') as file:
        json.dump(description, file, ensure_ascii=False)


def download_txt(link, page_info):
    book_path = page_info['book_path']
    response = requests.get(link)
    response.raise_for_status()
    with open(book_path, 'w', encoding='utf-8') as file:
        file.write(response.text)


def download_image(link, page_info):
    img_path = page_info['img_path']
    response = requests.get(link)
    response.raise_for_status()
    with open(img_path, 'wb') as file:
        file.write(response.content)


def get_args():
    parser = argparse.ArgumentParser(description='Программа для скачивания всех книг и обложек к нем,'
                                                 'со всех указанных страниц')
    parser.add_argument('-s', '--start_page', help='С какой страницы скачивать книги', type=int, default=1)
    parser.add_argument('-e', '--end_page', help='По какую страницу скачивать книги', type=int, default=4)
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = get_args()
    genre_url = 'https://tululu.org/l55/'
    logging.basicConfig(filename='sample.log', filemode='w',
                        format='%(filename)s - %(levelname)s - %(message)s',
                        level=logging.ERROR)
    all_books_urls = []
    books_folder = 'books'
    images_folder = 'images'
    json_folder = 'json'
    os.makedirs(books_folder, exist_ok=True)
    os.makedirs(images_folder, exist_ok=True)
    os.makedirs(json_folder, exist_ok=True)

    for page in range(args.start_page, args.end_page + 1):
        try:
            books_urls = get_books_urls(genre_url, page)
            all_books_urls.extend(books_urls)
        except ValueError:
            print(f'Страницы с номером {page} не существует')
            logging.error(f'Страницы с номером {page} не существует')
            if all_books_urls:
                print('Список ссылок на книги не пуст, скачивание продолжится')
            else:
                print('Никаких ссылок на книги не найдено, скачивание отменено')
            break

    books_description = []
    for url in tqdm(all_books_urls, ncols=90):
        book_id = urlsplit(url).path.strip('/').strip('b')
        try:
            book_link = get_book_link(book_id)
            book_page_info, img_link = parse_book_page(book_id, books_folder, images_folder)
            download_txt(book_link, book_page_info)
            download_image(img_link, book_page_info)
            books_description.append(book_page_info)
        except requests.HTTPError:
            print(f'Книга по ссылке {url} не доступна для скачивания')
            logging.error(f'Книга по ссылке {url} не доступна для скачивания')
            continue
    create_books_description(books_description, json_folder)
