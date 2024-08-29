import os
import urllib.parse
import requests
from bs4 import BeautifulSoup
import csv
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
}

class ImageDownloader:
    def __init__(self, image_folder="trendyol_image", driver_path='C:/Users/bozku/Downloads/chromedriver_win32/chromedriver.exe'):
        self.image_folder = image_folder
        self.downloaded_images = set()
        self.colors = []
        chrome_service = Service(executable_path=driver_path)
        self.driver = webdriver.Chrome(service=chrome_service)
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

    def clean_path(self, path):
        invalid_chars = '<>:"/\\|?*'
        path = str(path).translate({ord(c): "" for c in invalid_chars})
        path = path.replace('\xa0', ' ').strip('. ')
        return path[:255]

    def clean_file_name(self, file_name):
        file_name = file_name.split('?')[0]
        return self.clean_path(file_name)

    def download_image(self, url, categories, price, product, image_path, colors, soup, free_text, product_scraper):
        self.driver.get(url)
        time.sleep(3)
        product_id = product_scraper.extract_product_id(soup)
        img_elements = self.driver.find_elements(By.CSS_SELECTOR, 'div.product-slide img')

        for img_element in img_elements:
            img_url = img_element.get_attribute('src')
            if img_url and img_url.startswith('http'):
                img_url = img_url.replace("mnresize/128/192/", "mnresize/2000/2000/")
                try:
                    img_data = requests.get(img_url, timeout=10).content
                    file_name = f"{product_id}.jpg"
                    dir_path = os.path.join(self.image_folder, *[self.clean_path(cat) for cat in categories])
                    if not os.path.exists(dir_path):
                        os.makedirs(dir_path)
                    file_path = os.path.join(dir_path, file_name)

                    with open(file_path, 'wb') as file:
                        file.write(img_data)
                        print(f"Image successfully downloaded and saved: {file_path}")
                    time.sleep(2)
                except Exception as e:
                    print(f"Image could not be downloaded: {e}")

    def write_to_csv(self, categories, file_name, img_url, price, product_id, product, colors, free_text):
        csv_file_path = 'trendyol_output.csv'
        is_new_file = not os.path.exists(csv_file_path)

        brand = "trendyol"
        gender = "man"
        if len(categories) >= 2:
            master_category = categories[0]
            article_type = categories[1]
        else:
            master_category = article_type = "Category Information Not Available"

        color = ', '.join(colors) if isinstance(colors, list) else colors
        data_row = [brand, gender, master_category, article_type, color, product_id, price, free_text, f"{self.image_folder}/{file_name}", img_url]

        with open(csv_file_path, 'a', newline='', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file)
            if is_new_file:
                csv_writer.writerow(["Brand", "Gender", "Master_category", "Article_type", "Color", "Product_id", "Price", "Free_text", "Image_path", "Full_url"])
            csv_writer.writerow(data_row)

class ProductScraper:
    def __init__(self):
        pass

    def unique_ordered_list(self, seq):
        seen = set()
        return [x for x in seq if x not in seen and not seen.add(x)]

    def extract_free_text(self, soup):
        product_name_element = soup.find('h1', class_='pr-new-br')
        product_name = product_name_element.text.strip() if product_name_element else "Product Name Not Found"
        
        list_element = soup.find('ul', class_='detail-desc-list')
        free_text = "Detail Information Not Found"
        if list_element:
            list_items = list_element.find_all('li')
            free_text_items = list_items[5:]
            free_text = ' '.join(item.get_text(strip=True) for item in free_text_items)

        return product_name, free_text

    def extract_price(self, soup):
        price_element = soup.find('span', class_='prc-dsc')
        if price_element:
            return price_element.text.strip()
        return "Price Information Not Available"

    def get_product_links(self, page_url):
        try:
            response = requests.get(page_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                product_links = soup.find_all('div', class_='p-card-chldrn-cntnr card-border')
                links = [urllib.parse.urljoin(page_url, container.find('a')['href']) for container in product_links if container.find('a')]
                return links
            else:
                print(f"Page could not be loaded: {page_url}")
                return []
        except Exception as e:
            print(f"Error in get_product_links(): {e}")
            return []

    def extract_categories(self, link):
        try:
            response = requests.get(link, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                breadcrumb_links = soup.find_all('a', class_='product-detail-breadcrumb-item')
                self.colors = self.extract_colors(soup)

                categories = []
                if len(breadcrumb_links) > 4:
                    categories = [breadcrumb_links[2].text.strip(), breadcrumb_links[3].text.strip()]

                return categories
            else:
                print(f"Page could not be loaded: {link}")
                return []
        except Exception as e:
            print(f"Error in extract_categories(): {e}")
            return []

    def extract_colors(self, soup):
        color_elements = soup.select('.slc-img[title]')
        colors = [element.get('title') for element in color_elements if element.get('title')]
        return colors if colors else ['Multicolor']

    def extract_product_id(self, soup):
        product_header = soup.find('h1', class_='pr-new-br')
        if product_header:
            product_info = product_header.find('span')
            if product_info:
                product_text = product_info.text.strip()
                product_id = product_text.split()[-1]
                return product_id
        return None

class TrendyolCrawler:
    def __init__(self, image_folder="trendyol_image"):
        self.image_downloader = ImageDownloader(image_folder)
        self.product_scraper = ProductScraper()

    def get_total_product_count(self, url):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                description_element = soup.find('div', class_='dscrptn dscrptn-V2')
                if description_element:
                    text = description_element.text
                    numbers = re.findall(r'\d+', text)
                    return int(numbers[0]) if numbers else None
                else:
                    print("Total product count not found.")
                    return None
            else:
                print(f"Page could not be loaded, status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error in get_total_product_count(): {e}")
            return None

    def get_all_product_links_and_download(self, url, products_per_page=60, num_pages=None):
        total_products_count = self.get_total_product_count(url)
        if total_products_count is None:
            print("Total product count not found.")
            return

        current_page = 1
        while num_pages is None or current_page <= num_pages:
            page_url = f"{url}&page_size={products_per_page}&page={current_page}"
            links = self.product_scraper.get_product_links(page_url)

            if not links:
                print(f"No product links found for page {current_page}.")
                break

            for link in links:
                response = requests.get(link, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')

                categories = self.product_scraper.extract_categories(link)
                colors = self.product_scraper.extract_colors(soup)
                if not categories:
                    print(f"Category information not found, skipping this link: {link}")
                    continue

                price = self.product_scraper.extract_price(soup)
                product, free_text = self.product_scraper.extract_free_text(soup)
                print(f"Color information: {colors[0]} - {link}")
                print(f"Free text: {free_text}")

                image_path = os.path.join(self.image_downloader.image_folder, *categories)
                self.image_downloader.download_image(link, categories, price, product, image_path, colors, soup, free_text, self.product_scraper)
                print(f"Image download initiated: {link}")
            current_page += 1
            time.sleep(5)

        print("All product links and images have been processed.")
        
def main():
    url = 'https://www.trendyol.com/trendyol-man-erkek-x-b103500-g2'
    crawler = TrendyolCrawler()
    crawler.get_all_product_links_and_download(url)
    crawler.image_downloader.driver.quit()

if __name__ == "__main__":
    main()
