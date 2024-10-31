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
            save_out_of_stock_product({
                'url': product['url'],
                'name': product.get('name', 'Unknown'),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'reason': 'product_page_out_of_stock'
            })
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
        
        # Remove the redundant cart-contents check and go straight to data extraction
        logging.info("Extracting cart data")
        cart_data = extract_cart_data(driver, wait, rate_limiter)
        
        if cart_data:
            logging.info(f"Cart data extracted successfully:")
            for item in cart_data:
                logging.info(f"  - {item.get('name', 'Unknown')}")
                logging.info(f"    Price: {item.get('price', 'N/A')}")
                logging.info(f"    Quantity: {item.get('quantity', 'N/A')}")
            
            # Save cart data incrementally after successful extraction
            save_cart_data_incrementally(cart_data)
        else:
            logging.warning("No cart data was extracted")
        
        result = {
            'url': product['url'],
            'name': product.get('name', 'Unknown'),
            'added_to_cart': bool(cart_data),  # Only mark as successful if we got cart data
            'cart_data': cart_data
        }
        if cart_data:
            logging.info(f"Successfully processed product: {result['name']}")
            logging.info(f"Final result data: {json.dumps(result, indent=2)}")
        else:
            logging.error(f"Failed to process product {product['url']}: No cart data found")

        # After clicking add to cart, check for WooCommerce error message
        woo_errors = driver.find_elements(By.CSS_SELECTOR, "ul.woocommerce-error li")
        for error in woo_errors:
            if "because there is not enough stock" in error.text:
                logging.info(f"Product shows no stock after add to cart attempt: {product['name']}")
                save_out_of_stock_product({
                    'url': product['url'],
                    'name': product.get('name', 'Unknown'),
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'reason': 'add_to_cart_no_stock',
                    'error_message': error.text
                })
                return {
                    'url': product['url'],
                    'name': product.get('name', 'Unknown'),
                    'added_to_cart': False,
                    'status': 'out_of_stock'
                }

    except Exception as e:
        logging.error(f"Error processing product {product['url']}: {str(e)}")
        take_error_screenshot(driver, 'process_product_failed')
        result = {
            'url': product['url'],
            'name': product.get('name', 'Unknown'),
            'added_to_cart': False,
            'error': str(e)
        }
    finally:
        driver.quit()
    
    return result

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

def save_cart_data(cart_data, filename):
    if cart_data:
        fieldnames = ['name', 'price', 'quantity']
        
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(cart_data)
            
        logging.info(f"Cart data saved to {filename}")
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

def save_cart_data_incrementally(cart_data, filename="cart_contents.json"):
    """Save cart data to JSON file, merging with existing data"""
    try:
        # Load existing data if file exists
        if os.path.exists(filename):
            with open(filename, 'r') as file:
                existing_data = json.load(file)
        else:
            existing_data = []
            
        # Add new items and update existing ones
        for item in cart_data:
            normalized_new_name = normalize_product_name(item['name'])
            is_duplicate = any(
                normalize_product_name(existing_item['name']) == normalized_new_name
                for existing_item in existing_data
            )
            if not is_duplicate:
                existing_data.append(item)
                logging.info(f"Added new item to cart data: {item['name']}")
        
        # Save updated data
        with open(filename, 'w') as file:
            json.dump(existing_data, file, indent=2)
            
        logging.info(f"Cart data saved incrementally to {filename}")
    except Exception as e:
        logging.error(f"Error saving cart data incrementally: {str(e)}")

def normalize_product_name(name):
    """Normalize product name by removing variable fields and whitespace"""
    # Split into lines and filter out variable fields
    lines = [line.strip() for line in name.split('\n') if line.strip() and 
            not line.startswith(('Pet Name:', 'Doctor\'s Name:'))]
    return '\n'.join(lines)

def save_out_of_stock_product(product_data, filename="out_of_stock_products.json"):
    """Save out of stock product to JSON file, avoiding duplicates"""
    try:
        # Load existing data if file exists
        if os.path.exists(filename):
            with open(filename, 'r') as file:
                out_of_stock_products = json.load(file)
        else:
            out_of_stock_products = []
            
        # Check if product URL already exists
        if not any(item['url'] == product_data['url'] for item in out_of_stock_products):
            out_of_stock_products.append(product_data)
            
            # Save updated data
            with open(filename, 'w') as file:
                json.dump(out_of_stock_products, file, indent=2)
                
            logging.info(f"Added out of stock product to {filename}: {product_data['name']}")
            
    except Exception as e:
        logging.error(f"Error saving out of stock product data: {str(e)}")

def main():
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
