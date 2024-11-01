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
from site2_scraper.utils import take_error_screenshot, normalize_product_name

def process_single_product(product, rate_limiter, db, cookies=None):
    if not cookies:
        logging.error("No cookies provided to process_single_product")
        return {"url": product["url"], "name": product["name"], "added_to_cart": False}
        
    # Update status to processing using the database method
    db.update_processing_status(
        url=product['url'],
        name=product['name'],
        status='processing'
    )
    
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
                return {"url": product["url"], "name": product["name"], "added_to_cart": False}
        
        logging.info(f"Processing product: {product['name']} (URL: {product['url']})")
        
        rate_limiter.wait()
        driver.get(product['url'])
        logging.info(f"Navigated to product page: {product['url']}")
        add_random_delay(2, 4)
        
        # Check if product is out of stock on product page
        out_of_stock = driver.find_elements(By.CSS_SELECTOR, "p.stock.out-of-stock")
        if out_of_stock:
            logging.info(f"Product is out of stock: {product['name']}")
            db.mark_product_out_of_stock(product['url'], product['name'])
            db.update_processing_status(product['url'], product['name'], 'out_of_stock')
            return {
                'url': product['url'],
                'name': product.get('name', 'Unknown'),
                'added_to_cart': False,
                'status': 'out_of_stock'
            }
        
        # Check for WooCommerce error messages first
        woo_errors = driver.find_elements(By.CSS_SELECTOR, "ul.woocommerce-error li")
        for error in woo_errors:
            stock_error_phrases = [
                "not enough stock",
                "out of stock",
                "no stock available",
                "insufficient stock"
            ]
            if any(phrase in error.text.lower() for phrase in stock_error_phrases):
                logging.info(f"Product shows no stock after add to cart attempt: {product['name']}")
                db.mark_product_out_of_stock(product['url'], product['name'])
                db.update_processing_status(product['url'], product['name'], 'out_of_stock')
                return {
                    'url': product['url'],
                    'name': product.get('name', 'Unknown'),
                    'added_to_cart': False,
                    'status': 'out_of_stock'
                }
        
        # If we get redirected to login page, try to login again
        if "login" in driver.current_url.lower():
            logging.info("Session expired, logging in again")
            cookies = login(driver, wait, rate_limiter)
            driver.get(product['url'])  # Try to navigate to product again
        
        logging.info("Handling product variations")
        handle_variations(driver, wait)
        
        logging.info("Setting quantity to 1")
        quantity_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='quantity']")))
        quantity_input.clear()
        quantity_input.send_keys("30")
        
        logging.info("Clicking 'Add to Cart' button")
        add_to_cart_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".single_add_to_cart_button")))
        add_to_cart_button.click()
        
        logging.info("Waiting for redirect to product specification page")
        wait.until(EC.url_contains("product-specification-for-pet"))
        logging.info(f"Redirected to: {driver.current_url}")
        
        logging.info("Handling product specification form")
        handle_product_specification_form(driver, wait)
        
        logging.info("Waiting for redirect to cart page")
        wait.until(EC.url_contains("/cart-2/"))
        logging.info(f"Redirected to: {driver.current_url}")
        
        # Extract cart data
        logging.info("Extracting cart data")
        cart_data = extract_cart_data(driver, wait, rate_limiter)
        
        if cart_data:
            logging.info(f"Cart data extracted successfully:")
            for item in cart_data:
                logging.info(f"  - {item.get('name', 'Unknown')}")
                logging.info(f"    Price: {item.get('price', 'N/A')}")
                logging.info(f"    Quantity: {item.get('quantity', 'N/A')}")
            
            # Save cart data incrementally after successful extraction
            save_cart_data_incrementally(cart_data, db)
            db.update_processing_status(product['url'], product['name'], 'completed')
            return {
                'url': product['url'],
                'name': product['name'],
                'added_to_cart': True,
                'cart_data': cart_data
            }
        else:
            logging.warning("No cart data was extracted")
            db.update_processing_status(product['url'], product['name'], 'failed', 'No cart data extracted')
            return {
                'url': product['url'],
                'name': product['name'],
                'added_to_cart': False,
                'status': 'failed'
            }

    except Exception as e:
        error_msg = str(e)
        logging.error(f"Failed to process product {product['url']}: {error_msg}")
        take_error_screenshot(driver, 'process_product_failed')
        
        # Mark the product as failed and update its status
        db.mark_product_failed(product['url'], product['name'], error_msg)
        db.update_processing_status(product['url'], product['name'], 'failed', error_msg)
        
        return {
            'url': product['url'],
            'name': product.get('name', 'Unknown'),
            'added_to_cart': False,
            'error': error_msg
        }
    finally:
        driver.quit()

def handle_variations(driver, wait):
    try:
        # Try different selectors for variations
        selectors = [
            "select[data-attribute_name]",  # Original selector
            "div.variations select",        # General variations selector
            "div.vp-form select.select"     # The new structure you found
        ]
        
        variation_selects = []
        for selector in selectors:
            try:
                elements = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                if elements:
                    variation_selects.extend(elements)
                    logging.info(f"Found variations using selector: {selector}")
            except TimeoutException:
                logging.debug(f"No variations found with selector: {selector}")
                continue
        
        if not variation_selects:
            logging.info("No variations found for this product")
            return
            
        for select in variation_selects:
            try:
                # Log the select element details for debugging
                logging.debug(f"Attempting to select variation: {select.get_attribute('name')} / {select.get_attribute('id')}")
                
                # Wait for element to be clickable
                wait.until(EC.element_to_be_clickable(select))
                
                # Get all available options
                select_element = Select(select)
                options = select_element.options
                
                # Skip if only has default option
                if len(options) <= 1:
                    logging.debug(f"Skipping select with insufficient options: {select.get_attribute('name')}")
                    continue
                
                # Select first non-default option
                select_element.select_by_index(1)
                logging.info(f"Successfully selected option for: {select.get_attribute('name')}")
                time.sleep(1)  # Small delay between selections
                
            except Exception as e:
                logging.debug(f"Could not select variation: {str(e)}")
                # Take screenshot on failure
                take_error_screenshot(driver, 'variation_selection_failed')
                continue
                
    except Exception as e:
        logging.debug(f"Error handling variations: {str(e)}")
        take_error_screenshot(driver, 'variations_handling_failed')

def handle_additional_options(driver, wait):
    """Handle additional options on the next page if necessary"""
    try:
        # Wait for the page to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Look for select elements
        select_elements = driver.find_elements(By.TAG_NAME, "select")
        
        for select_element in select_elements:
            select = Select(select_element)
            options = select.options
            if len(options) > 1:
                select.select_by_index(1)  # Select the second option (index 1)
        
        add_random_delay(1, 2)
        
        # Look for a submit or continue button
        buttons = driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit'], .continue-button")
        if buttons:
            buttons[0].click()
            logging.info("Clicked submit/continue button")
        else:
            logging.info("No submit/continue button found")
        
    except Exception as e:
        logging.warning(f"Error handling additional options: {str(e)}")

def extract_cart_data(driver, wait, rate_limiter):
    """Extract data from the cart page"""
    try:
        rate_limiter.wait_if_needed()
        driver.get(config.CART_URL)
        
        # Wait for the page to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Check if we're on the cart page
        if "cart" not in driver.current_url.lower():
            logging.warning(f"Not on cart page. Current URL: {driver.current_url}")
            return []
        
        # Wait for the cart table to load
        cart_table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.shop_table.cart")))
        
        cart_items = cart_table.find_elements(By.CSS_SELECTOR, "tr.cart_item")
        
        if not cart_items:
            logging.warning("No items found in the cart.")
            logging.info(f"Page source: {driver.page_source}")
            return []
        
        cart_data = []
        for item in cart_items:
            try:
                name = item.find_element(By.CSS_SELECTOR, "td.product-name").text.strip()
                price = item.find_element(By.CSS_SELECTOR, "td.product-subtotal span.amount").text.strip()
                quantity = item.find_element(By.CSS_SELECTOR, "td.product-quantity input.qty").get_attribute('value')
                
                cart_data.append({
                    'name': name,
                    'price': price,
                    'quantity': quantity
                })
            except Exception as e:
                logging.error(f"Error extracting data for an item: {str(e)}")
        
        return cart_data
        
    except Exception as e:
        logging.error(f"Failed to extract cart data: {str(e)}")
        logging.error(f"Current URL: {driver.current_url}")
        take_error_screenshot(driver, 'cart_extraction_error')
        return []

def save_cart_data(cart_data, db):
    if cart_data:
        db.save_cart_data(cart_data)
        logging.info(f"Cart data saved to database")
    else:
        logging.warning("No cart data to save")

def handle_product_specification_form(driver, wait):
    """Handle product specifications if present"""
    try:
        logging.info("Looking for product specification form")
        form = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "form[name='prospmain']")))
        logging.info("Product specification form found")
        
        logging.info("Selecting pet name")
        pet_name_select = Select(form.find_element(By.ID, "petidname"))
        pet_name_select.select_by_index(1)  # Select the first non-empty option
        
        logging.info("Selecting number of refills")
        refill_select = Select(form.find_element(By.ID, "no_of_refillforclinic"))
        refill_select.select_by_value("1")  # Select 1 refill
        
        logging.info("Selecting doctor")
        doctor_select = Select(form.find_element(By.ID, "doctoridforp"))
        doctor_select.select_by_index(1)  # Select the first non-empty option
        
        logging.info("Clicking continue button")
        continue_button = form.find_element(By.ID, "continuebutton")
        continue_button.click()
        
        logging.info("Waiting for form submission")
        wait.until(EC.staleness_of(form))
        logging.info("Form submitted successfully")
        
    except Exception as e:
        logging.error(f"Error handling product specification form: {str(e)}")
        logging.info(f"Current URL: {driver.current_url}")
        logging.info(f"Page source: {driver.page_source[:1000]}...")  # Log first 1000 chars of page source
        raise

def save_cart_data_incrementally(cart_data, db):
    """Save cart data to database, merging with existing data"""
    try:
        existing_data = db.get_cart_data()
        new_items = []
        
        for item in cart_data:
            details_new = normalize_product_name(item['name'])
            is_duplicate = any(
                normalize_product_name(existing_item['name'])['name'] == details_new['name']
                for existing_item in existing_data
            )
            
            if not is_duplicate:
                new_items.append(item)
                logging.info(f"New item identified: {details_new['name']}")
        
        if new_items:
            db.save_cart_data(new_items)
            logging.info(f"Added {len(new_items)} new items to cart data")
        else:
            logging.info("No new items to add")
            
    except Exception as e:
        logging.error(f"Error saving cart data incrementally: {str(e)}")


def save_out_of_stock_product(product_data, db):
    """Save out of stock product to database, avoiding duplicates"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # First check if product already exists
            cursor.execute('''
                SELECT id FROM out_of_stock_products 
                WHERE url = ? OR name = ?
            ''', (product_data['url'], product_data['name']))
            
            existing = cursor.fetchone()
            if existing:
                logging.info(f"Product already marked as out of stock: {product_data['name']}")
                return False
            
            # If not exists, insert new record
            cursor.execute('''
                INSERT INTO out_of_stock_products (name, url, reason, error_message, timestamp)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                product_data['name'],
                product_data['url'],
                product_data.get('reason', 'unknown'),
                product_data.get('error_message', '')
            ))
            conn.commit()
            
            logging.info(f"Added out of stock product to database: {product_data['name']}")
            return True
            
    except Exception as e:
        logging.error(f"Error saving out of stock product data: {str(e)}")
        return False

""" def main():
    logging.basicConfig(
        level=logging.INFO,
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
    
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as f:
            all_product_links = json.load(f)
        logging.info(f"Loaded {len(all_product_links)} product links from {json_file_path}")
    else:
        all_product_links = collect_product_links(rate_limiter)

    if not all_product_links:
        logging.error("No product links collected. Exiting.")
        return

    # Login once at the start and save cookies
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

    # Process products in parallel with saved cookies
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_single_product, product, rate_limiter, cookies) 
                  for product in all_product_links]
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result and result['added_to_cart']:
                cart_manager.add_product(result)

    # Extract and save cart data
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        login(driver, wait, rate_limiter)
        cart_data = extract_cart_data(driver, wait, rate_limiter)
        
        if cart_data:
            filename = "cart_contents.json"
            
            # Load existing data if the file exists
            if os.path.exists(filename):
                with open(filename, 'r') as file:
                    existing_data = json.load(file)
            else:
                existing_data = []
            
            # Merge new data with existing data, avoiding duplicates
            for item in cart_data:
                normalized_new_name = normalize_product_name(item['name'])
                is_duplicate = any(
                    normalize_product_name(existing_item['name']) == normalized_new_name
                    for existing_item in existing_data
                )
                if not is_duplicate:
                    existing_data.append(item)
            
            # Save merged data to JSON file
            with open(filename, 'w') as file:
                json.dump(existing_data, file, indent=2)
                
            logging.info(f"Cart data saved to {filename}")
        else:
            logging.warning("No cart data to save")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
 """