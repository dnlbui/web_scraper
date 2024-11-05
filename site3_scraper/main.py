import logging
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from concurrent.futures import ThreadPoolExecutor
import json
import os

from site3_scraper.browser_actions import login, collect_product_links, apply_cookies
from site3_scraper.data_processing import process_single_product
from common.rate_limiter import RateLimiter
from site3_scraper import config
from site3_scraper.database import Database

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('price_scraper.log'),
            logging.StreamHandler()
        ]
    )

def process_product_urls(urls, rate_limiter, db, cookies):
    """Process a list of product URLs and extract price information"""
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        if not apply_cookies(driver, cookies):
            logging.error("Failed to apply cookies. Exiting.")
            return []

        results = []
        for url in urls:
            logging.info(f"Processing URL: {url}")
            try:
                product_data = process_single_product(driver, wait, url)
                if product_data:
                    logging.info(f"Attempting to save product data for: {url}")
                    logging.debug(f"Product data: {product_data}")
                    db.save_product_price(product_data)
                    logging.info(f"Successfully saved product data for: {url}")
                    results.append(product_data)
                else:
                    logging.warning(f"No product data returned for: {url}")
            except Exception as e:
                logging.error(f"Error processing URL {url}: {str(e)}")
                continue

        return results

    except Exception as e:
        logging.error(f"Error in process_product_urls: {str(e)}")
        return []
    finally:
        driver.quit()

def main():
    parser = argparse.ArgumentParser(description='Product price scraper')
    parser.add_argument('--input-file', type=str, help='JSON file containing product URLs')
    parser.add_argument('--show-progress', action='store_true', help='Show current processing status')
    parser.add_argument('--collect-urls', action='store_true', help='Collect product URLs from website first')
    args = parser.parse_args()

    setup_logging()
    logging.info("Starting price scraper...")
    
    db = Database('site3_scraper.db')
    rate_limiter = RateLimiter(max_requests=config.MAX_REQUESTS, time_window=config.TIME_WINDOW)

    if args.show_progress:
        progress = db.get_processing_status()
        for status, count in progress.items():
            print(f"{status}: {count} products")
        return

    # Initialize browser and get cookies first
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    try:
        cookies = login(driver, wait, rate_limiter)
        if not cookies:
            logging.error("Initial login failed. Exiting.")
            return
        logging.info("Successfully obtained login cookies")
    finally:
        driver.quit()

    if args.collect_urls:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        wait = WebDriverWait(driver, 10)
        try:
            if apply_cookies(driver, cookies):
                urls = collect_product_links(driver, wait, rate_limiter)
                logging.info(f"Collected {len(urls)} product URLs")
        finally:
            driver.quit()
        return

    # Load URLs from input file or site2_scraper database
    if args.input_file and os.path.exists(args.input_file):
        with open(args.input_file, 'r') as f:
            urls = json.load(f)
        logging.info(f"Loaded {len(urls)} URLs from {args.input_file}")
    else:
        urls = db.get_urls_from_site2_db()
        if not urls:
            logging.error("No URLs found in site2_scraper database")
            return

    # Add counters
    total_urls = len(urls)
    processed_urls = 0
    failed_urls = 0

    # Process URLs in batches with shared cookies
    def process_batch(batch):
        nonlocal processed_urls, failed_urls
        results = process_product_urls(batch, rate_limiter, db, cookies)
        processed_urls += len(results)
        failed_urls += len(batch) - len(results)
        return results

    batch_size = min(10, len(urls))
    with ThreadPoolExecutor(max_workers=20) as executor:  # Reduced workers
        futures = []
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            logging.info(f"Processing batch {i//batch_size + 1} of {len(urls)//batch_size + 1}")
            future = executor.submit(process_batch, batch)
            futures.append(future)
        
        # Wait for all futures to complete
        for future in futures:
            try:
                future.result()
            except Exception as e:
                logging.error(f"Batch processing failed: {str(e)}")

    logging.info(f"Processing complete:")
    logging.info(f"Total URLs: {total_urls}")
    logging.info(f"Successfully processed: {processed_urls}")
    logging.info(f"Failed: {failed_urls}")

    # Export results to JSON
    results = db.get_all_results()
    with open('price_data.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logging.info("Price scraper finished. Results saved to price_data.json")

if __name__ == "__main__":
    main()