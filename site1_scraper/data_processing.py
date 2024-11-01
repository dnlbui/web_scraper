import logging
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from site2_scraper import config
from site2_scraper.browser_actions import login, add_random_delay, apply_cookies
from common.rate_limiter import RateLimiter
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import concurrent.futures
from site2_scraper.utils import take_error_screenshot

def process_single_product(product, rate_limiter, cookies=None):
    if not cookies:
        logging.error("No cookies provided to process_single_product")
        return {"url": product["url"], "name": product["name"], "added_to_cart": False}
        
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 45)
    
    try:
        # First navigate to the domain (required before setting cookies)
        driver.get(config.BASE_URL)
        
        # Apply cookies and verify login status
        if apply_cookies(driver, cookies):
            logging.info("Successfully applied cookies")
            add_random_delay(1, 2)
        else:
            logging.warning("Failed to apply cookies, attempting new login")
            cookies = login(driver, wait, rate_limiter)
            if not cookies:
                logging.error("Failed to obtain new cookies")

def save_to_csv(all_products, filename, full_description=False):
    if all_products:
        try:
            fieldnames = ['name', 'url', 'description']
            
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, 
                                    fieldnames=fieldnames,
                                    delimiter=',',
                                    quoting=csv.QUOTE_ALL)
                
                writer.writeheader()
                
                for product in all_products:
                    description = clean_description(product['description'], full_description)
                    cleaned_product = {
                        'name': product['name'].strip(),
                        'url': product['url'].strip(),
                        'description': description
                    }
                    writer.writerow(cleaned_product)
            
            logging.info(f"\nData successfully written to {filename}")
        except Exception as e:
            logging.error(f"Failed to write to CSV file: {str(e)}")

def save_to_json(all_products, filename, full_description=False):
    if all_products:
        try:
            cleaned_products = []
            for product in all_products:
                description = clean_description(product['description'], full_description)
                cleaned_product = {
                    'name': product['name'].strip(),
                    'url': product['url'].strip(),
                    'description': description
                }
                cleaned_products.append(cleaned_product)
            
            with open(filename, 'w', encoding='utf-8') as file:
                json.dump(cleaned_products, file, ensure_ascii=False, indent=2)
            
            logging.info(f"\nData successfully written to {filename}")
        except Exception as e:
            logging.error(f"Failed to write to JSON file: {str(e)}")

def clean_description(description, full_description=False):
    description = (description
        .strip()
        .replace('\n', ' ')
        .replace('\r', ' ')
        .replace('\t', ' ')
        .replace('"', "'"))
    
    description = ' '.join(description.split())
    
    if not full_description and len(description) > 500:
        description = description[:500].rsplit(' ', 1)[0] + "..."
    
    return description
