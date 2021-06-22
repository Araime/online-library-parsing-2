import argparse
import json
import logging
import os
from pathvalidate import sanitize_filename
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import requests
from tqdm import tqdm


def get_end_page_number(genre_url):
    response = requests.get(genre_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'lxml')
    end_page_number = int(soup.select('.npage')[-1].text)
    return end_page_number


def get_books_urls(genre_url, page_number, end_page_number):
    if page > end_page_number:
        raise ValueError(f'Страницы под номером {page_number} не существует')

    page_url = f'{genre_url}{page_number}'
    response = requests.get(page_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    books = soup.select('.d_book')
    books_ids = [book.a['href'] for book in books]
    books_links = [urljoin('https://tululu.org', id_number) for id_number in books_ids]
    return books_links


def get_book_link(book_id):
    base_url = f'https://tululu.org/txt.php'
    payload = {'id': book_id}
    response = requests.get(base_url, params=payload)
    check_for_redirect(response)
    return response.url


def check_for_redirect(response):
    if response.history:
        raise requests.HTTPError(response.history)


def parse_book_page(book_id, book_folder, image_folder):
    book_page_link = f'https://tululu.org/b{book_id}'
    response = requests.get(book_page_link)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    title_tag = soup.select_one('h1')
    title = title_tag.text.split('::')
    book_name = sanitize_filename(title[0].strip())
    author = title[1].strip()
    img = soup.select_one('.bookimage a img')['src']
    filename = img.split('/')[-1]
    img_src = os.path.join(image_folder, filename)
    book_path = os.path.join(book_folder, f'{book_name}.txt')
    image_link = urljoin('https://tululu.org', img)
    comments_tags = soup.select('.texts')
    comments = [comment.span.text for comment in comments_tags]
    genre_tag = soup.select('span.d_book a')
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


def create_books_description(description, folder):
    json_path = os.path.join(folder, 'books_description.json')
    with open(json_path, 'w', encoding='utf-8') as file:
        json.dump(description, file, ensure_ascii=False)


def get_args():
    parser = argparse.ArgumentParser(description='Программа для скачивания всех книг и обложек к нем,'
                                                 'со всех указанных страниц')
    parser.add_argument('-s', '--start_page', help='С какой страницы скачивать книги', type=int, default=1)
    parser.add_argument('-e', '--end_page', help='До какой страницы скачивать книги', type=int)
    arguments = parser.parse_args()
    return arguments


if __name__ == '__main__':
    args = get_args()
    logging.basicConfig(filename='sample.log', filemode='w',
                        format='%(filename)s - %(levelname)s - %(message)s',
                        level=logging.ERROR)
    genre_url = 'https://tululu.org/l55/'
    end_page_number = get_end_page_number(genre_url)
    all_books_urls = []
    books_folder = 'books/'
    images_folder = 'images/'
    json_folder = 'json/'
    os.makedirs(books_folder, exist_ok=True)
    os.makedirs(images_folder, exist_ok=True)
    os.makedirs(json_folder, exist_ok=True)

    start_page = args.start_page
    if args.end_page:
        end_page = args.end_page
    else:
        end_page = end_page_number

    for page in range(start_page, end_page):
        try:
            books_urls = get_books_urls(genre_url, page, end_page_number)
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
