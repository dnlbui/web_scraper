import logging
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
import argparse
import json

from site1_scraper.browser_actions import collect_product_links
from site1_scraper.data_processing import process_single_product, save_to_csv, save_to_json
from common.rate_limiter import RateLimiter
from site1_scraper import config

def main():
    parser = argparse.ArgumentParser(description='Web scraper for product information')
    parser.add_argument('--json', action='store_true', help='Save output as JSON instead of CSV')
    parser.add_argument('--full-description', action='store_true', help='Do not limit description length')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scraper_debug.log'),
            logging.StreamHandler()
        ]
    )
    
    logging.info("\nStarting web scraper...")
    
    rate_limiter = RateLimiter(max_requests=config.MAX_REQUESTS, time_window=config.TIME_WINDOW)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        all_product_links = collect_product_links(driver, wait, rate_limiter)
        logging.info(f"\nCollected total of {len(all_product_links)} product links")
    finally:
        driver.quit()
    
    all_products = []
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        future_to_product = {executor.submit(process_single_product, product, rate_limiter): product 
                           for product in all_product_links}
        
        for future in future_to_product:
            result = future.result()
            if result:
                all_products.append(result)
                logging.info(f"Added product to final list: {result['name']}")
    
    if args.json:
        save_to_json(all_products, config.OUTPUT_FILE.replace('.csv', '.json'), args.full_description)
    else:
        save_to_csv(all_products, config.OUTPUT_FILE, args.full_description)

if __name__ == "__main__":
    main()
