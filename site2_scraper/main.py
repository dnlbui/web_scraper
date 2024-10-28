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

from site2_scraper.browser_actions import login, add_product_to_cart, collect_product_links, add_random_delay, get_product_variations, select_variation, set_quantity
from site2_scraper.data_processing import handle_product_specification_form, process_single_product, extract_cart_data, save_cart_data
from common.rate_limiter import RateLimiter
from site2_scraper import config

class CartManager:
    def __init__(self):
        self.product_queue = queue.Queue() # Thread-safe queue for products

    def add_product(self, product):
        self.product_queue.put(product) # Add products to queue

def add_to_cart_from_queue(cart_manager, rate_limiter):
    """Process products from the queue and add them to cart"""
    # Creates a new browser instance
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        while True:
            try:
                # Get next product from queue with timeout
                product_data = cart_manager.product_queue.get(timeout=30)
                
                # Login first (for each product, to ensure we're always logged in)
                login(driver, wait, rate_limiter)
                
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
                continue
                
    finally:
        driver.quit()

def is_product_processed(product, existing_cart_data):
    """Check if a product with specific variations has been processed"""
    for existing_item in existing_cart_data:
        if (product['name'] == existing_item['name'] and
            product.get('variations', {}) == existing_item.get('variations', {})):
            return True
    return False

def process_product_variations(product_url, rate_limiter):
    """Process all variations for a single product"""
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        wait = WebDriverWait(driver, 45)
        variation_tracker = ProductVariationTracker()
        
        # Get current status
        status = variation_tracker.get_product_status(product_url)
        
        # Get all possible variations first
        logging.info("Getting initial login to check variations")
        login(driver, wait, rate_limiter)  # Initial login to check variations
        
        rate_limiter.wait()
        driver.get(product_url)
        add_random_delay(2, 4)
        
        variations = get_product_variations(driver, wait)
        logging.info(f"Found {len(variations)} variations to process")
        
        # Close initial browser
        driver.quit()
        
        # Process each variation with a new browser instance
        for variation in variations:
            variation_key = json.dumps(variation, sort_keys=True)
            if variation_key in status['variations_tried']:
                logging.info(f"Skipping already tried variation: {variation}")
                continue
                
            logging.info(f"Processing variation: {variation}")
            process_single_variation(product_url, variation, variation_tracker, rate_limiter)
            
    except Exception as e:
        logging.error(f"Error processing product {product_url}: {str(e)}")
    finally:
        if driver and driver.service.is_connectable():
            driver.quit()

def process_single_variation(product_url, variation, variation_tracker, rate_limiter):
    """Process a single variation with its own browser instance"""
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        wait = WebDriverWait(driver, 45)
        
        # Login for this variation
        logging.info("Logging in for new variation")
        login(driver, wait, rate_limiter)
        
        # Navigate to product
        rate_limiter.wait()
        driver.get(product_url)
        add_random_delay(2, 4)
        
        # Select the variation options
        select_variation(driver, wait, variation)
        
        # Set quantity
        set_quantity(driver, wait, config.DEFAULT_QUANTITY)
        
        # Create product data dictionary before add_product_to_cart call
        product_data = {
            'url': product_url,
            'variations': variation
        }
        
        # Add to cart
        add_product_to_cart(driver, wait, product_data, rate_limiter)
        
        # Handle product specification form if needed
        handle_product_specification_form(driver, wait)
        
        # Mark as succeeded
        variation_tracker.update_variation_status(product_url, variation, success=True)
        logging.info(f"Successfully added variation: {variation}")
        
    except Exception as e:
        logging.error(f"Failed to add variation {variation}: {str(e)}")
        variation_tracker.update_variation_status(product_url, variation, success=False)
    finally:
        if driver:
            driver.quit()

def main():
    # Add argument parsing
    parser = argparse.ArgumentParser(description='Cart scraper with source selection')
    parser.add_argument('--use-warnings', action='store_true', 
                       help='Use failed_products.json instead of product_links.json')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,  # Change to DEBUG for even more detailed logs
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('cart_scraper.log'),
            logging.StreamHandler()
        ]
    )
    
    logging.info("Starting cart scraper...")
    rate_limiter = RateLimiter(max_requests=20, time_window=60)
    cart_manager = CartManager()
    
    json_file_path = 'product_links.json'
    failed_products_path = 'failed_products.json'
    cart_contents_file = 'cart_contents.json'
    
    # Load existing cart data if available
    existing_cart_data = []
    if os.path.exists(cart_contents_file):
        with open(cart_contents_file, 'r') as f:
            existing_cart_data = json.load(f)
        logging.info(f"Loaded {len(existing_cart_data)} existing items from {cart_contents_file}")

    # Load product links based on flag
    if args.use_warnings:
        logging.info("Using failed_products.json as source")
        if os.path.exists(failed_products_path):
            with open(failed_products_path, 'r') as f:
                all_product_links = json.load(f)
            logging.info(f"Loaded {len(all_product_links)} product links from {failed_products_path}")
        else:
            logging.error(f"Failed products file not found at {failed_products_path}. Exiting.")
            return
    else:
        logging.info("Using product_links.json as source")
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r') as f:
                all_product_links = json.load(f)
            logging.info(f"Loaded {len(all_product_links)} product links from {json_file_path}")
        else:
            logging.warning(f"Product links file not found at {json_file_path}. Collecting new links.")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            wait = WebDriverWait(driver, 10)
            try:
                all_product_links = collect_product_links(driver, wait, rate_limiter)
            finally:
                driver.quit()

    if not all_product_links:
        logging.error("No product links collected. Exiting.")
        return

    # Filter out products that are already in cart
    products_to_process = []
    skipped_products = 0
    
    for product in all_product_links:
        if is_product_processed(product, existing_cart_data):
            logging.info(f"Skipping already processed product: {product['name']} "
                        f"with variations: {product.get('variations', {})}")
            skipped_products += 1
            continue
        products_to_process.append(product)

    logging.info(f"Found {skipped_products} already processed products")
    logging.info(f"Processing {len(products_to_process)} new products in parallel with {config.MAX_WORKERS} workers")

    successful_additions = 0
    failed_additions = 0
    
    if products_to_process:
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            futures = [executor.submit(process_single_product, product, rate_limiter) 
                      for product in products_to_process]
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result and result['added_to_cart']:
                    cart_manager.add_product(result)
                    logging.info(f"Successfully added product to cart: {result['name']} (URL: {result['url']})")
                    successful_additions += 1
                else:
                    logging.warning(f"Failed to add product to cart: {result.get('name', 'Unknown')} (URL: {result.get('url', 'Unknown')})")
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
            filename = "cart_contents.json"
            
            if os.path.exists(filename):
                with open(filename, 'r') as file:
                    existing_data = json.load(file)
                logging.info(f"Loaded {len(existing_data)} existing items from {filename}")
            else:
                existing_data = []
                logging.info(f"No existing data found, creating new file {filename}")
            
            new_items_count = 0
            updated_items_count = 0
            for item in cart_data:
                existing_item = next((i for i in existing_data if i['name'] == item['name']), None)
                if existing_item:
                    if existing_item != item:
                        existing_item.update(item)
                        updated_items_count += 1
                        logging.info(f"Updated item in cart data: {item['name']}")
                else:
                    existing_data.append(item)
                    new_items_count += 1
                    logging.info(f"Added new item to cart data: {item['name']}")
            
            with open(filename, 'w') as file:
                json.dump(existing_data, file, indent=2)
            
            logging.info(f"Cart data saved to {filename}. Added {new_items_count} new items.")
        else:
            logging.warning("No cart data extracted. Cart might be empty.")
    except Exception as e:
        logging.error(f"Error during cart data extraction and saving: {str(e)}")
        logging.exception("Traceback:")
    finally:
        driver.quit()

    logging.info("Cart scraper finished.")

if __name__ == "__main__":
    main()
