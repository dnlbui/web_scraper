import logging
from concurrent.futures import ThreadPoolExecutor
from telnetlib import EC
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
import queue
import csv
from selenium.webdriver.common.by import By
import json
import os
import concurrent.futures
import time
import argparse
import sys

from site2_scraper.browser_actions import login, add_product_to_cart, collect_product_links, add_random_delay
from site2_scraper.data_processing import normalize_product_name, process_single_product, extract_cart_data, save_cart_data, save_cart_data_incrementally
from common.rate_limiter import RateLimiter
from site2_scraper import config
from site2_scraper.database import Database

class CartManager:
    def __init__(self, db):
        self.db = db
        self.product_queue = queue.Queue()  # Change from self.queue to self.product_queue

    def add_product(self, product_data):
        existing_data = self.db.get_cart_data()
        product_details = normalize_product_name(product_data.get('name', ''))
        
        is_duplicate = any(
            normalize_product_name(item['name'])['name'] == product_details['name']
            for item in existing_data
        )
        
        if not is_duplicate:
            self.product_queue.put(product_data)  # Use put() method for Queue
            if 'cart_data' in product_data:
                self.db.save_cart_data(product_data['cart_data'])
            logging.info(f"Added new product to cart: {product_details['name']}")
        else:
            logging.info(f"Skipping duplicate product: {product_details['name']}")

    def get_queue(self):
        return list(self.product_queue.queue)  # Convert Queue to list for viewing

def add_to_cart_from_queue(cart_manager, rate_limiter):
    """Process products from the queue and add them to cart"""
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        wait = WebDriverWait(driver, 10)
        
        # First navigate to base domain and login
        driver.get(config.BASE_URL)
        cookies = login(driver, wait, rate_limiter)
        logging.info("Initial login successful, cookies captured")

        if not cookies:
            logging.error("No cookies obtained from initial login. Exiting.")
            return

        while True:
            try:
                # Get next product from queue with timeout
                product_data = cart_manager.product_queue.get(timeout=30)
                
                # Navigate to product page
                rate_limiter.wait()
                driver.get(product_data['url'])
                add_random_delay(2, 4)
                
                # Add to cart using stored dropdown values
                add_product_to_cart(driver, wait, product_data, rate_limiter)
                
                cart_manager.product_queue.task_done()
                add_random_delay(2, 4)
                
            except queue.Empty:
                logging.info("No more products to process")
                break
            except Exception as e:
                logging.error(f"Error adding product to cart: {str(e)}")
                try:
                    driver.quit()
                    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
                    wait = WebDriverWait(driver, 10)
                    driver.get(config.BASE_URL)
                    cookies = login(driver, wait, rate_limiter)
                except Exception as login_error:
                    logging.error(f"Failed to re-login: {str(login_error)}")
                continue
                
    except Exception as e:
        logging.error(f"Error in add_to_cart_from_queue: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser(description='Cart scraper with source selection')
    parser.add_argument('--use-warnings', action='store_true', 
                       help='Use failed_products table instead of product_links table')
    parser.add_argument('--show-progress', action='store_true',
                       help='Show current processing status')
    args = parser.parse_args()

    if args.show_progress:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    status, 
                    COUNT(*) as count,
                    MAX(last_attempt) as last_processed
                FROM processing_status 
                GROUP BY status
            ''')
            for row in cursor.fetchall():
                print(f"Status: {row[0]}, Count: {row[1]}, Last processed: {row[2]}")
        return

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('cart_scraper.log'),
            logging.StreamHandler()
        ]
    )
    
    logging.info("Starting cart scraper...")
    rate_limiter = RateLimiter(max_requests=20, time_window=60)
    # Initialize database and cart manager
    db = Database()
    cart_manager = CartManager(db)
    existing_cart_data = db.get_cart_data()
    logging.info(f"Loaded {len(existing_cart_data)} existing items from database")

    # Reset any stuck 'processing' status items
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE processing_status 
            SET status = 'pending'
            WHERE status = 'processing'
        ''')
        conn.commit()

    # Load or collect product links based on flag
    if args.use_warnings:
        logging.info("Using failed_products table as source")
        all_product_links = db.get_product_links()
        logging.info(f"Loaded {len(all_product_links)} product links from failed_products table")
    else:
        logging.info("Using product_links table as source")
        all_product_links = db.get_product_links()
        if not all_product_links:
            logging.info("No links in database, collecting new product links...")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            wait = WebDriverWait(driver, 10)
            try:
                all_product_links = collect_product_links(driver, wait, rate_limiter)
                if all_product_links:
                    db.save_product_links(all_product_links)
                    logging.info(f"Saved {len(all_product_links)} links to database")
            finally:
                driver.quit()
        logging.info(f"Loaded {len(all_product_links)} product links")

    if not all_product_links:
        logging.error("No product links collected. Exiting.")
        return

    # Filter out products that are already in cart
    products_to_process = []
    skipped_products = 0
    
    for product in all_product_links:
        if any(item['name'] == product['name'] for item in existing_cart_data):
            logging.info(f"Skipping already processed product: {product['name']}")
            skipped_products += 1
            continue
        products_to_process.append(product)

    logging.info(f"Found {skipped_products} already processed products")
    logging.info(f"Processing {len(products_to_process)} new products in parallel with {config.MAX_WORKERS} workers")

    # Initialize processing status for new products
    with db.get_connection() as conn:
        cursor = conn.cursor()
        for product in products_to_process:
            cursor.execute('''
                INSERT OR IGNORE INTO processing_status (url, name, status)
                VALUES (?, ?, 'pending')
            ''', (product['url'], product['name']))
        conn.commit()

    # Get products that need processing (pending or failed)
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT url, name FROM processing_status 
            WHERE status IN ('pending', 'failed')
            AND (last_attempt IS NULL OR 
                 datetime(last_attempt, '+1 hour') < datetime('now'))
            ORDER BY last_attempt ASC NULLS FIRST
            LIMIT ?
        ''', (config.MAX_WORKERS * 2,))  # Get twice the number of workers to ensure enough work
        products_to_process = [{'url': row[0], 'name': row[1]} 
                             for row in cursor.fetchall()]
        
    logging.info(f"Found {len(products_to_process)} products to process")

    # Login once at the start and get cookies
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    cookies = None
    
    try:
        driver.get(config.BASE_URL)
        cookies = login(driver, wait, rate_limiter)
        logging.info("Initial login successful, cookies captured")
    except Exception as e:
        logging.error(f"Initial login failed: {str(e)}")
        raise
    finally:
        driver.quit()

    if not cookies:
        logging.error("No cookies obtained from initial login. Exiting.")
        return

    # Process products in parallel with saved cookies
    successful_additions = 0
    failed_additions = 0
    
    if products_to_process:
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            futures = [
                executor.submit(
                    process_single_product, 
                    product, 
                    rate_limiter, 
                    db,  
                    cookies
                ) 
                for product in products_to_process
            ]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        if result.get('status') == 'out_of_stock':
                            logging.info(f"Product out of stock: {result['name']}")
                            failed_additions += 1
                        elif result['added_to_cart']:
                            cart_manager.add_product(result)
                            logging.info(f"Successfully processed: {result['name']}")
                            successful_additions += 1
                        else:
                            logging.warning(f"Failed to process: {result['name']}")
                            failed_additions += 1
                except Exception as e:
                    logging.error(f"Error processing future: {str(e)}")
                    failed_additions += 1
    else:
        logging.info("No new products to process")

    logging.info(f"Product addition summary: {successful_additions} successful, {failed_additions} failed")

    logging.info("Processing cart queue")
    add_to_cart_from_queue(cart_manager, rate_limiter)

    logging.info("Extracting and saving cart data")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        login(driver, wait, rate_limiter)
        cart_data = extract_cart_data(driver, wait, rate_limiter)
        
        if cart_data:
            logging.info(f"Extracted {len(cart_data)} items from cart")
            save_cart_data_incrementally(cart_data, db)
            logging.info("Cart data saved to database")
        else:
            logging.warning("No cart data to extract")
    except Exception as e:
        logging.error(f"Error extracting cart data: {str(e)}")
        logging.exception("Traceback:")
    finally:
        driver.quit()

    logging.info("Cart scraper finished.")

if __name__ == "__main__":
    main()
