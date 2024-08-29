import os
import urllib.parse
import requests
from bs4 import BeautifulSoup
import csv
import re
import time

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
}

class ImageDownloader:
    def __init__(self, image_folder="mavi_image"):
        self.image_folder = image_folder
        self.downloaded_images = set()

        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

    def clean_path(self, path):
        path = str(path)
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            path = path.replace(char, '')
        path = path.replace('\xa0', ' ')  # Replace non-breaking space with regular space
        path = path[:255]
        return path.strip('. ')

    def clean_file_name(self, file_name):
        file_name = file_name.split('?')[0]  # Remove query strings
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            file_name = file_name.replace(char, '')
        file_name = file_name.replace('\xa0', ' ')  # Replace non-breaking space with regular space
        file_name = file_name[:255]  # Respect filename length limit for Windows
        return file_name

    def download_image(self, url, categories, price, product):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                swiper_wrapper = soup.find('div', {'id': 'swiper-wrapper'})
                if swiper_wrapper:
                    img_tags = swiper_wrapper.find_all('img')
                    for img_tag in img_tags:
                        img_url = img_tag['src']
                        if img_url.startswith('//'):
                            img_url = 'https:' + img_url  # Add protocol
                        if img_url in self.downloaded_images:
                            continue
                        product_code_tag = soup.find('div', class_='product__color-name')
                        if product_code_tag:
                            product_code = product_code_tag.get_text(strip=True).split(' - ', 1)[0]
                        else:
                            product_code = "Unknown"
                        if self.check_product_code_in_csv(product_code):
                            print(f"Product code {product_code} already exists in CSV. Skipping download.")
                            continue
                        img_data = requests.get(img_url).content
                        file_name = self.clean_file_name(img_url.split('/')[-1])
                        dir_path = os.path.join(self.image_folder, *[self.clean_path(cat) for cat in categories])
                        os.makedirs(dir_path, exist_ok=True)
                        file_path = os.path.join(dir_path, file_name)
                        with open(file_path, 'wb') as file:
                            file.write(img_data)
                            self.downloaded_images.add(img_url)
                            self.write_to_csv(categories, file_name, "", img_url, dir_path, price, product)
                else:
                    print("Image gallery not found.")
        except Exception as e:
            print(f"Error in download_image(): {e}")

    def check_product_code_in_csv(self, product_code):
        try:
            csv_file_path = 'mavi_output.csv'
            if not os.path.exists(csv_file_path):
                return False

            with open(csv_file_path, 'r', encoding='utf-8') as csv_file:
                csv_reader = csv.reader(csv_file)
                for row in csv_reader:
                    if row and row[6] == product_code:
                        return True

            return False
        except Exception as e:
            print(f"Error in check_product_code_in_csv(): {e}")
            return False

    def write_to_csv(self, categories, file_name, alt_text, img_url, image_path, price, product):
        try:
            csv_file_path = 'mavi_output.csv'
            is_new_file = not os.path.exists(csv_file_path)
            with open(csv_file_path, 'a', newline='', encoding='utf-8') as csv_file:
                csv_writer = csv.writer(csv_file)
                if is_new_file:
                    csv_writer.writerow(["Brand", "Gender", "Master_category", "Article_type", "Color", "Product_id", "Price", "Free_text", "Image_path", "Full_url", "Label", "BBOX", "Bytea", "Label_path", "Created_at"])
                csv_writer.writerow(["mavi", "woman"] + categories + [price] + [f"{product}" f"{alt_text}"] + [f"{image_path}\{file_name}", img_url])
                self.downloaded_images.add(img_url)
                print(f"{file_name} saved to {image_path}.")
        except Exception as e:
            print(f"Error in write_to_csv(): {e}")

class ProductScraper:
    def __init__(self):
        pass

    def clean_free_text(self, text):
        text = re.sub(r'\s+', ' ', text)  # Replace all whitespace sequences with a single space
        text = re.sub(r'\xa0', ' ', text)  # Replace non-breaking space with regular space
        text = text.replace('/\n', ' ').replace('\n', ' ')  # Replace new line characters with space
        text = text.strip()  # Strip leading and trailing whitespace
        return text

    def extract_price(self, soup):
        price_element = soup.find('div', class_='product__product-pricing')
        if price_element:
            prices = price_element.text.strip().split('\n')
            prices = [price.strip() for price in prices if price.strip()]
            if prices:
                return prices[0]
        return "Price Information Not Available"

    def get_product_links(self, page_url):
        try:
            response = requests.get(page_url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                product_links = soup.find_all('a', class_='product-card-info')
                links = [urllib.parse.urljoin(page_url, link['href']) for link in product_links]
                return links
            else:
                print(f"Page could not be loaded: {page_url}")
                return []
        except Exception as e:
            print(f"Error in get_product_links(): {e}")
            return []

    def extract_categories(self, link):
        try:
            response = requests.get(link)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                breadcrumb_links = soup.find_all('li', class_='breadcrumb__list-item')
                categories = [link.text.strip() for index, link in enumerate(breadcrumb_links[2:]) if link.text.strip() and index != 1]
                product = []

                color_tag = soup.find('div', class_='product__color-name')
                if color_tag:
                    content = color_tag.get_text(strip=True)
                    color = content.split(' - ', 1)[1] if ' - ' in content else content
                    categories.append(f"{color}")
                else:
                    print("Color information not found.")

                product_code_tag = soup.find('div', class_='product__color-name')
                if product_code_tag:
                    content = product_code_tag.get_text(strip=True)
                    product_code = content.split(' - ', 1)[0]
                    categories.append(product_code)
                else:
                    print("Product code information not found.")

                price = self.extract_price(soup)
                features_content_div = soup.find('div', class_='product__features--content accordion__item--content')
                if features_content_div:
                    all_text = features_content_div.get_text(separator=' ', strip=True)
                    clean_text = self.clean_free_text(all_text)
                    product.append(clean_text)
                else:
                    print("Relevant feature section not found.")
                return categories, price, product
            else:
                print(f"Page could not be loaded: {link}")
                return []
        except Exception as e:
            print(f"Error in extract_categories(): {e}")
            return []

class MaviCrawler:
    def __init__(self, image_folder="mavi_image"):
        self.image_downloader = ImageDownloader(image_folder)
        self.product_scraper = ProductScraper()

    def get_total_product_count(self, url):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                total_products_element = soup.find('div', class_='right-menu-item product-number')
                if total_products_element:
                    total_products_text = total_products_element.get_text(strip=True)
                    total_products_count = int(total_products_text.split()[0].replace('.', ''))
                    return total_products_count
                else:
                    print("Total product count not found.")
                    return None
            else:
                print(f"Page could not be loaded: {url}")
                return None
        except Exception as e:
            print(f"Error in get_total_product_count(): {e}")
            return None

    def get_all_product_links_and_download(self, url, products_per_page=60, num_pages=None):
        total_products_count = self.get_total_product_count(url)
        if total_products_count is not None:
            current_page = 1
            while num_pages is None or current_page <= num_pages:
                page_url = url
                links = self.product_scraper.get_product_links(page_url)
                if not links:
                    break
                for link in links:
                    categories, price, product = self.product_scraper.extract_categories(link)
                    self.image_downloader.download_image(link, categories, price, product)
                    time.sleep(10)
                current_page += 1
                time.sleep(10)
            print("All product links and images have been downloaded.")

def main():
    url = 'https://www.mavi.com/kadin/c/1'
    crawler = MaviCrawler()
    crawler.get_all_product_links_and_download(url)

if __name__ == "__main__":
    main()
