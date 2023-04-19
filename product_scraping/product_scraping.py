import json
import requests
from bs4 import BeautifulSoup as bs
import os
import pandas as pd
import datetime
import csv
import re
import numpy as np
import config

def get_current_time_str():
    now = datetime.datetime.now()
    time_str = now.strftime("%H:%M:%S")
    return time_str


scraper_api_url = f"http://api.scraperapi.com?api_key={config.SCRAPER_API_KEY}="

dir = os.path.dirname(__file__)

categories_filename = os.path.join(dir, "categories.json")
categories = None
with open(categories_filename) as file:
    categories = json.load(file)

main_cat_counter = 1
NUM_RETRIES = 3
all_products = []
base_target_url = "https://www.sephora.sg"
print("Start scraping products")
for main_cat in categories:
    print(f"{get_current_time_str()}: processing {main_cat_counter}/{len(categories.keys())} main categories - {main_cat}")
    sub_cat_counter = 1
    for sub_cat in categories[main_cat]:
        print(
            f"{get_current_time_str()}: processing {sub_cat_counter}/{len(categories[main_cat].keys())} sub categories - {sub_cat}")
        sub_cat_urls = categories[main_cat][sub_cat]
        products_html = []
        target_url = f"{scraper_api_url}{base_target_url}{sub_cat_urls[0]}"
        for _ in range(NUM_RETRIES):
            try:
                response = requests.get(target_url)
                if response.status_code in [200, 404]:
                    # escape for loop if the API returns a successful response
                    # or when the requested page can't be found on the website server
                    break
            except requests.exceptions.ConnectionError:
                response = ''

        try:
            if response.status_code != 200:
                print(f"Failed to get response for {sub_cat} - target url: {target_url}")
                continue
            soup = bs(response.content, 'html.parser')
            current_pg_products = soup.find_all(
                'div', class_="products-card-container")
            products_html.extend(current_pg_products)

            # get all pages for this sub_cat and get the products in each pg (apart from the 1st pg which was already scraped)
            paginations = soup.find_all(
                'nav', class_="pagination bottom-pagination")[0].find_all('a')
            for pagination in paginations:
                sub_cat_urls.append(pagination['href'])
            sub_cat_urls = pd.unique(sub_cat_urls)
            categories[main_cat][sub_cat] = sub_cat_urls
            for i in range(1, len(sub_cat_urls)):
                target_url = f"{scraper_api_url}{base_target_url}{sub_cat_urls[i]}"
                for _ in range(NUM_RETRIES):
                    try:
                        response = requests.get(target_url)
                        if response.status_code in [200, 404]:
                            # escape for loop if the API returns a successful response
                            # or when the requested page can't be found on the website server
                            break
                    except requests.exceptions.ConnectionError:
                        response = ''
                if response.status_code != 200:
                    print(f"Failed to get response for {sub_cat} - target url: {target_url}")
                    continue
                soup = bs(response.content, 'html.parser')
                current_pg_products = soup.find_all(
                    'div', class_="products-card-container")
                products_html.extend(current_pg_products)

            # get product details
            for ph in products_html:
                main_div = ph.find_all('div')[0]
                raw_product_name = main_div["data-product-name"]
                cleaned_product_name = re.sub("[\"']", "", raw_product_name)
                cleaned_product_name = re.sub("&", "and", cleaned_product_name)
                brand = main_div["data-product-brand"]
                product_img_link = main_div.find_all(
                    'img', class_="product-card-image")[0]["src"]
                product_url = base_target_url + \
                    main_div.find_all(
                        'a', class_="product-card-image-link")[0]["href"]
                product = {"main_category": main_cat, "sub_category": sub_cat, "raw_product_name": raw_product_name,
                           "cleaned_product_name": cleaned_product_name, "product_url": product_url, "brand": brand, "product_img_link": product_img_link}
                all_products.append(product)
            print(f"There are a total of {len(products_html)} {sub_cat} products")
            sub_cat_counter += 1
        except Exception as e:
            print(
                f"Something went wrong with main category: {main_cat}, sub category: {sub_cat}")
            print(e)

    main_cat_counter += 1


print(f"There are a total of {len(all_products)} products")
df = pd.DataFrame(all_products)
products_filename = os.path.join(dir, "products.csv")
df.to_csv(products_filename, encoding='utf-8',
          index=False, quoting=csv.QUOTE_MINIMAL)
print("Done scraping products")

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

try:
    with open(categories_filename, "w") as write_file:
        json.dump(categories, write_file, indent=4, cls=NumpyEncoder)
except Exception as e:
    print(f"Something went wrong with updating {categories_filename}")
    print(e)
