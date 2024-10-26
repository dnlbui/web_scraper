import logging
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait

from browser_actions import collect_product_links
from data_processing import process_single_product, save_to_csv
from common.rate_limiter import RateLimiter
import config

def main():
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
    
    save_to_csv(all_products, config.OUTPUT_FILE)

if __name__ == "__main__":
    main()
