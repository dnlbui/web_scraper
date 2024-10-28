import time
import logging
import random
import json
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from site2_scraper import config
from retrying import retry

# Login credentials
SITE2_USERNAME = os.getenv("SITE2_USERNAME")
SITE2_PASSWORD = os.getenv("SITE2_PASSWORD")

def add_random_delay(min_seconds=2, max_seconds=5):
    time.sleep(random.uniform(min_seconds, max_seconds))

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def login_with_retry(driver, wait, rate_limiter):
    """Handle site login"""
    try:
        rate_limiter.wait()  # Changed from wait_if_needed() to wait()
        driver.get(config.LOGIN_URL)
        time.sleep(random.uniform(2, 4))
        
        username = wait.until(EC.presence_of_element_located((By.ID, "username")))
        password = driver.find_element(By.ID, "passwordl")  # Note the 'l' at the end
        
        # Simulate human typing
        for char in config.SITE2_USERNAME:
            username.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))
        
        for char in config.SITE2_PASSWORD:
            password.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))
        
        time.sleep(random.uniform(1, 2))
        login_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Login']")
        login_button.click()
        
        # Wait for URL to change, indicating successful login
        wait.until(EC.url_changes(config.LOGIN_URL))
        
        # Additional check for successful login
        if "login" not in driver.current_url.lower():
            logging.info(f"Successfully logged in. Current URL: {driver.current_url}")
        else:
            raise Exception("Login failed: Still on login page after submission")
        
        time.sleep(random.uniform(3, 5))
        
    except Exception as e:
        logging.error(f"Login failed: {str(e)}")
        logging.error(f"Current URL: {driver.current_url}")
        logging.error(f"Page source: {driver.page_source}")
        raise

def login(driver, wait, rate_limiter):
    try:
        login_with_retry(driver, wait, rate_limiter)
    except Exception as e:
        logging.error(f"Failed to log in after 3 attempts: {str(e)}")
        raise

def add_product_to_cart(driver, wait, product_data, rate_limiter):
    """Handle the process of adding a single product to cart"""
    try:
        rate_limiter.wait()
        
        # Navigate to product page if URL provided
        if 'url' in product_data:
            driver.get(product_data['url'])
            add_random_delay(1, 2)
        
        # Set quantity first (if field exists)
        try:
            quantity_input = wait.until(EC.presence_of_element_located((By.ID, "quantity")))
            quantity_input.clear()
            quantity_input.send_keys(config.QUANTITY)
            add_random_delay(1, 2)
        except Exception as e:
            logging.warning(f"Failed to set quantity: {str(e)}")
        
        # Select variations if provided
        if product_data.get('variations'):
            select_variation(driver, wait, product_data['variations'])
            add_random_delay(1, 2)
        
        # Click add to cart button
        add_to_cart_button = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "a.single_add_to_cart_button, button.single_add_to_cart_button")))
        add_to_cart_button.click()
        add_random_delay(2, 3)
        
        # Handle the prescription form that appears
        try:
            # Wait for the form to appear
            form = wait.until(EC.presence_of_element_located((By.ID, "prospmainforp")))
            
            # Select pet name (first option)
            pet_select = wait.until(EC.presence_of_element_located((By.ID, "petidname")))
            pet_select = Select(pet_select)
            options = pet_select.options
            # Select first non-empty option that's not "Add Another Pet"
            for option in options:
                if option.get_attribute("value") and option.get_attribute("value") != "" and option.get_attribute("value") != "Add Another Pet":
                    pet_select.select_by_value(option.get_attribute("value"))
                    break
            add_random_delay(0.5, 1)
            
            # Select number of refills (select "0")
            refill_select = wait.until(EC.presence_of_element_located((By.ID, "no_of_refillforclinic")))
            refill_select = Select(refill_select)
            refill_select.select_by_value("0")
            add_random_delay(0.5, 1)
            
            # Select doctor (first available)
            doctor_select = wait.until(EC.presence_of_element_located((By.ID, "doctoridforp")))
            doctor_select = Select(doctor_select)
            options = doctor_select.options
            # Select first non-empty option that's not "Another Doctor"
            for option in options:
                if option.get_attribute("value") and option.get_attribute("value") != "" and option.get_attribute("value") != "Another Doctor":
                    doctor_select.select_by_value(option.get_attribute("value"))
                    break
            add_random_delay(0.5, 1)
            
            # Click continue button
            continue_button = wait.until(EC.element_to_be_clickable(
                (By.ID, "continuebutton")))
            continue_button.click()
            add_random_delay(2, 3)
            
            # Wait for success message or cart update
            success = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, 
                ".woocommerce-message, .cart-updated, .woocommerce-error, .cart-contents"
            )))
            
            if "error" not in success.get_attribute("class"):
                logging.info(f"Successfully added product to cart: {product_data.get('url')}")
                
                # Extract cart data
                cart_items = []
                items = driver.find_elements(By.CSS_SELECTOR, ".cart_item")
                for item in items:
                    item_data = {
                        'name': item.find_element(By.CSS_SELECTOR, ".product-name").text,
                        'price': item.find_element(By.CSS_SELECTOR, ".product-price").text,
                        'quantity': item.find_element(By.CSS_SELECTOR, ".product-quantity input").get_attribute("value"),
                        'variations': product_data.get('variations', {}),
                        'url': product_data.get('url')
                    }
                    cart_items.append(item_data)
                
                # Save cart data incrementally
                save_cart_data_incrementally(cart_items)
            else:
                raise Exception(f"Error adding to cart: {success.text}")
                
        except Exception as e:
            logging.error(f"Failed to fill prescription form: {str(e)}")
            raise
            
    except Exception as e:
        logging.error(f"Failed to add product to cart: {str(e)}")
        raise

def navigate_to_sorted_products(driver, wait, rate_limiter):
    try:
        rate_limiter.wait_if_needed()
        driver.get(config.PRODUCTS_PAGE_URL)
        logging.info(f"Navigating to sorted products page: {config.PRODUCTS_PAGE_URL}")
        
        # Wait for the page to load
        wait_long = WebDriverWait(driver, 30)  # Increase timeout to 30 seconds
        
        # Try different selectors
        selectors = [".product_area", ".bow_maker", ".bow_text", ".woocommerce-result-count"]
        for selector in selectors:
            try:
                wait_long.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                logging.info(f"Page loaded successfully. Found element with selector: {selector}")
                break
            except TimeoutException:
                logging.warning(f"Selector {selector} not found within timeout period")
        else:
            raise TimeoutException("None of the expected elements were found on the page")

        # Log the page title and URL for debugging
        logging.info(f"Current page title: {driver.title}")
        logging.info(f"Current URL: {driver.current_url}")
        
        # Check if we're on the correct page
        if "product-category/prescription-medicines" not in driver.current_url:
            logging.error("Not on the expected product category page")
            raise Exception("Navigation failed: Not on the expected product category page")

        add_random_delay(2, 4)
        logging.info("Successfully navigated to sorted products page")
    except Exception as e:
        logging.error(f"Failed to navigate to sorted products page: {str(e)}")
        logging.error(f"Current URL: {driver.current_url}")
        raise

def collect_product_links(driver, wait, rate_limiter):
    all_product_links = []
    page = 1
    json_file_path = 'product_links.json'

    # Check if the JSON file already exists
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as f:
            all_product_links = json.load(f)
        logging.info(f"Loaded {len(all_product_links)} product links from {json_file_path}")
        return all_product_links

    try:
        # First, ensure we're logged in
        login(driver, wait, rate_limiter)
        logging.info(f"Login completed. Current URL: {driver.current_url}")

        # Navigate to the product page
        driver.get(config.PRODUCTS_PAGE_URL)
        logging.info(f"Navigated to products page. Current URL: {driver.current_url}")

        while True:
            logging.info(f"Collecting links from page {page}")
            
            # Log the current page source for debugging
            logging.debug(f"Current page source: {driver.page_source[:500]}...")  # Log first 500 chars

            try:
                # Wait for the product area to load
                product_area = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product_area")))
            except TimeoutException:
                logging.warning(f"Timeout waiting for product area on page {page}")
                driver.save_screenshot(f"debug_screenshot_page_{page}_before_refresh.png")
                logging.info(f"Screenshot saved: debug_screenshot_page_{page}_before_refresh.png")
                
                # Try to refresh the page and wait again
                driver.refresh()
                try:
                    product_area = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product_area")))
                except TimeoutException:
                    logging.error(f"Failed to load product area on page {page} after refresh")
                    driver.save_screenshot(f"debug_screenshot_page_{page}_after_refresh.png")
                    logging.info(f"Screenshot saved: debug_screenshot_page_{page}_after_refresh.png")
                    logging.error(f"Current URL after failed refresh: {driver.current_url}")
                    break

            # Find all product containers
            products = driver.find_elements(By.CLASS_NAME, "product_area")
            
            if not products:
                logging.warning(f"No products found on page {page}")
                break
            
            for product in products:
                try:
                    # Find the link within the product's bow_text div
                    link_element = product.find_element(By.CSS_SELECTOR, ".bow_text a")
                    link = link_element.get_attribute('href')
                    name = link_element.text.strip()
                    all_product_links.append({'url': link, 'name': name})
                    logging.info(f"Collected product: {name} - {link}")
                except NoSuchElementException:
                    logging.warning(f"Could not find link for a product on page {page}")
            
            # Check if there's a next page
            try:
                next_page = driver.find_element(By.CSS_SELECTOR, "a.next.page-numbers")
                next_page.click()
                page += 1
                rate_limiter.wait()
            except NoSuchElementException:
                logging.info("No more pages to scrape")
                break
            
    except Exception as e:
        logging.error(f"Error in collect_product_links: {str(e)}", exc_info=True)
    
    logging.info(f"Collected a total of {len(all_product_links)} product links")
    # After collecting all links, save them to a JSON file
    with open(json_file_path, 'w') as f:
        json.dump(all_product_links, f)
    logging.info(f"Saved {len(all_product_links)} product links to {json_file_path}")
    return all_product_links

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
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'variations': {
                        value['attribute']: value['value']
                        for value in combination['values']
                    }
                })
                
                return True
                
            except Exception as e:
                logging.warning(f"Failed to select combination {combination['values']}: {str(e)}")
                continue
        
        return False
            
    except Exception as e:
        logging.error(f"Error handling variations: {str(e)}")
        return False

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

def get_product_variations(driver, wait, url):  # Add url parameter
    """Get all possible variations for a product"""
    try:
        logging.info("Waiting for variations form...")
        form = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "form.variations_form, span.variations_form"))
        )
        
        # Get the variations data from the data attribute
        variations_data = form.get_attribute('data-product_variations')
        if variations_data:
            variations = json.loads(variations_data)
            logging.info(f"Found {len(variations)} variations in data attribute")
            
            # Save variations data
            save_variations_data(url, variations)
            
            # Extract the first variation's attributes as our default selection
            if variations:
                first_variation = variations[0]
                return first_variation.get('attributes', {})
            
        logging.info("No variations found in data attribute, checking for select elements...")
        
        # Fallback to select elements if no data attribute
        selects = driver.find_elements(By.CSS_SELECTOR, "select[data-attribute_name]")
        if not selects:
            logging.info("No variation dropdowns found")
            return None
            
        # Get all options for each dropdown
        variation_data = {}
        for select in selects:
            name = select.get_attribute('data-attribute_name')
            select_element = Select(select)
            # Get first non-empty option
            options = [opt.text for opt in select_element.options if opt.text.strip() and "Choose an option" not in opt.text]
            if options:
                variation_data[name] = options[0]  # Take first option
                logging.info(f"Selected variation '{name}': {options[0]}")
        
        return variation_data if variation_data else None
        
    except Exception as e:
        logging.error(f"Error getting variations: {str(e)}", exc_info=True)
        return None

def select_variation(driver, wait, variations):
    """Select product variations from dropdowns"""
    try:
        for attribute, value in variations.items():
            # Remove 'attribute_' prefix if it exists
            attr_name = attribute.replace('attribute_', '')
            select_name = f"attribute_{attr_name}"
            
            # Wait for and find the select element with a longer timeout
            try:
                select_element = wait.until(
                    EC.presence_of_element_located((By.NAME, select_name))
                )
                select = Select(select_element)
                
                # Try both value and visible text
                try:
                    select.select_by_value(value)
                except:
                    # Try cleaning up the value (e.g., "1.25mg" -> "1-25mg")
                    cleaned_value = value.replace('.', '-')
                    try:
                        select.select_by_value(cleaned_value)
                    except:
                        select.select_by_visible_text(value)
                
                logging.info(f"Selected variation {select_name}={value}")
                add_random_delay(1, 2)  # Longer delay between selections
                
            except Exception as e:
                logging.warning(f"Failed to set variation {select_name}={value}: {str(e)}")
                # Continue with other variations instead of failing completely
                continue
                
    except Exception as e:
        logging.error(f"Error selecting variations: {str(e)}")
        raise

def generate_combinations(options_dict):
    """Generate all possible combinations of options"""
    import itertools
    
    keys = list(options_dict.keys())
    values = list(options_dict.values())
    combinations = []
    
    for combination in itertools.product(*values):
        combinations.append(dict(zip(keys, combination)))
    
    return combinations

def set_quantity(driver, wait, quantity):
    quantity_input = wait.until(EC.presence_of_element_located((By.NAME, "quantity")))
    quantity_input.clear()
    quantity_input.send_keys(str(quantity))

def save_variations_data(url, variations_data):
    """Save variations data to JSON file"""
    try:
        filename = 'variations.json'
        data = {}
        
        # Load existing data if file exists
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
        
        # Add new variations data
        data[url] = variations_data
        
        # Save updated data
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
            
    except Exception as e:
        logging.error(f"Error saving variations data: {str(e)}")


