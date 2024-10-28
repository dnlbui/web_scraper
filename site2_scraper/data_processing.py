import logging
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from scraper2 import CartManager
from site1_scraper.browser_actions import collect_product_links
from site2_scraper import config
from site2_scraper.browser_actions import (
    login, 
    add_random_delay, 
    get_product_variations,  
    select_variation,       
    add_product_to_cart     
)
from common.rate_limiter import RateLimiter
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import concurrent.futures

def process_single_product(product, rate_limiter):
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 45)
    
    try:
        logging.info(f"Processing product: {product['name']} (URL: {product['url']}")
        
        login(driver, wait, rate_limiter)
        
        rate_limiter.wait()
        driver.get(product['url'])
        add_random_delay(2, 4)
        
        # Get and handle variations
        variations = get_product_variations(driver, wait)
        if variations:
            logging.info(f"Found variations: {variations}")
            # Create product data for cart addition
            product_data = {
                'url': product['url'],
                'variations': variations  # Pass the variations dictionary directly
            }
            
            # Use the dedicated function to add to cart
            add_product_to_cart(driver, wait, product_data, rate_limiter)
        else:
            logging.warning(f"No variations found for product: {product['name']}")
            
    except Exception as e:
        logging.error(f"Error processing product {product['url']}: {str(e)}")
        logging.error("Traceback:", exc_info=True)
    finally:
        driver.quit()
    
    return result

def handle_variations(driver, wait, product_url, combinations_tracker):
    """Handle all possible combinations of product variations"""
    try:
        # Wait for variations to be present
        variation_selects = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "select[data-attribute_name]"))
        )
        
        if not variation_selects:
            logging.info("No variations found for this product")
            return True
        
        # Get all options for each variation
        variations = []
        for select in variation_selects:
            select_element = Select(select)
            # Skip first option if it's a placeholder (like "Choose an option")
            options = select_element.options[1:] if len(select_element.options) > 1 else select_element.options
            variations.append({
                'select': select_element,
                'options': options,
                'attribute': select.get_attribute('data-attribute_name')
            })
        
        # Get completed combinations
        completed_combinations = combinations_tracker.get_completed_combinations(product_url)
        
        # Try each combination
        for combination in get_next_combination(variations, completed_combinations):
            try:
                # Select each option in the combination
                for var_idx, option_idx in enumerate(combination['indices']):
                    variations[var_idx]['select'].select_by_index(option_idx + 1)  # +1 to skip placeholder
                    time.sleep(1)
                
                # Save the successful combination
                combinations_tracker.save_combination(product_url, {
                    'combination': combination['values'],
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                })
                
                return True
                
            except Exception as e:
                logging.warning(f"Failed to select combination {combination['values']}: {str(e)}")
                continue
        
        return False
            
    except Exception as e:
        logging.error(f"Error handling variations: {str(e)}")
        return False

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
        logging.error(f"Page source: {driver.page_source}")
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

def create_product_key(item):
    """Create a unique key for a product including its variations"""
    # Get the base product name
    base_name = normalize_product_name(item['name'])
    
    # Get variation data
    variations = item.get('variations', {})
    strength = variations.get('strength', '')
    quantity = variations.get('quantity', '')
    
    # Create a unique key combining all elements
    key = f"{base_name}|{strength}|{quantity}"
    return key

def save_cart_data_incrementally(cart_data, filename="cart_contents.json"):
    """Save cart data to JSON file, merging with existing data"""
    try:
        # Load existing data if file exists
        if os.path.exists(filename):
            with open(filename, 'r') as file:
                existing_data = json.load(file)
        else:
            existing_data = []
            
        # Create a dictionary of existing items by their unique keys
        existing_keys = {create_product_key(item): item for item in existing_data}
        
        # Add or update items
        for item in cart_data:
            key = create_product_key(item)
            if key not in existing_keys:
                existing_data.append(item)
                logging.info(f"Added new item to cart data: {item['name']} with variations: {item.get('variations', {})}")
            else:
                # Optionally update existing item if needed
                if existing_keys[key] != item:
                    existing_keys[key].update(item)
                    logging.info(f"Updated existing item: {item['name']} with variations: {item.get('variations', {})}")
        
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

    # Process products in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_single_product, product, rate_limiter) 
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

class ProductCombinationsTracker:
    def __init__(self, base_dir="product_combinations"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        
    def _get_product_filename(self, product_url):
        """Generate a safe filename from product URL"""
        product_id = product_url.split('/')[-2]  # Get the slug from URL
        return os.path.join(self.base_dir, f"{product_id}_combinations.json")
    
    def get_completed_combinations(self, product_url):
        """Get previously completed combinations for a product"""
        filename = self._get_product_filename(product_url)
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return []
    
    def save_combination(self, product_url, combination_data):
        """Save a completed combination"""
        filename = self._get_product_filename(product_url)
        completed = self.get_completed_combinations(product_url)
        
        # Add new combination if not already present
        if combination_data not in completed:
            completed.append(combination_data)
            with open(filename, 'w') as f:
                json.dump(completed, f, indent=2)

def get_next_combination(variations, completed_combinations):
    """Generator for getting next untried combination"""
    # Get all possible combinations
    option_counts = [len(var['options']) for var in variations]
    total_combinations = 1
    for count in option_counts:
        total_combinations *= count
    
    for i in range(total_combinations):
        # Calculate indices for this combination
        indices = []
        remainder = i
        for count in reversed(option_counts):
            indices.insert(0, remainder % count)
            remainder //= count
        
        # Get the actual values for these indices
        values = []
        for var_idx, opt_idx in enumerate(indices):
            values.append({
                'attribute': variations[var_idx]['attribute'],
                'value': variations[var_idx]['options'][opt_idx].text
            })
        
        # Skip if this combination was already completed
        if any(comb['combination'] == values for comb in completed_combinations):
            continue
            
        yield {
            'indices': indices,
            'values': values
        }

class ProductVariationTracker:
    def __init__(self, base_dir="product_variations"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
    
    def _get_product_filename(self, product_url):
        """Generate a safe filename from product URL"""
        product_id = product_url.split('/')[-2]
        return os.path.join(self.base_dir, f"{product_id}_variations.json")
    
    def get_product_status(self, product_url):
        """Get the status of all variations for a product"""
        filename = self._get_product_filename(product_url)
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return {
            'url': product_url,
            'variations_tried': [],
            'variations_succeeded': [],
            'variations_failed': [],
            'is_complete': False
        }
    
    def update_variation_status(self, product_url, variation, success=True):
        """Update the status of a specific variation"""
        status = self.get_product_status(product_url)
        variation_key = json.dumps(variation, sort_keys=True)
        
        if variation_key not in status['variations_tried']:
            status['variations_tried'].append(variation_key)
            
        if success:
            if variation_key not in status['variations_succeeded']:
                status['variations_succeeded'].append(variation_key)
        else:
            if variation_key not in status['variations_failed']:
                status['variations_failed'].append(variation_key)
        
        self._save_status(product_url, status)
        
    def _save_status(self, product_url, status):
        """Save the current status to file"""
        filename = self._get_product_filename(product_url)
        with open(filename, 'w') as f:
            json.dump(status, f, indent=2)

