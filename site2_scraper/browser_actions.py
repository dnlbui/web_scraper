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
from site2_scraper.utils import take_error_screenshot

# Login credentials
SITE2_USERNAME = os.getenv("SITE2_USERNAME")
SITE2_PASSWORD = os.getenv("SITE2_PASSWORD")

def add_random_delay(min_seconds=2, max_seconds=5):
    time.sleep(random.uniform(min_seconds, max_seconds))

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def login_with_retry(driver, wait, rate_limiter):
    """Handle site login and return cookies"""
    try:
        rate_limiter.wait()
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
        
        # After successful login, get cookies
        cookies = driver.get_cookies()
        if not cookies:
            logging.error("No cookies obtained after successful login")
            return None
            
        logging.info("Successfully captured login cookies")
        return cookies
        
    except Exception as e:
        logging.error(f"Login failed: {str(e)}")
        take_error_screenshot(driver, 'login_failed')
        return None

def apply_cookies(driver, cookies):
    """Apply saved cookies to a new browser session"""
    if not cookies:
        logging.error("No cookies provided to apply_cookies")
        return False
        
    try:
        for cookie in cookies:
            driver.add_cookie(cookie)
        logging.info("Applied saved cookies to browser session")
        # Refresh the page to activate cookies
        driver.refresh()
        add_random_delay(1, 2)
        
        # Verify login status (you might need to adjust this based on your site)
        if "login" in driver.current_url.lower():
            logging.warning("Still on login page after applying cookies")
            return False
            
        return True
    except Exception as e:
        logging.warning(f"Failed to apply cookies: {str(e)}")
        return False

def login(driver, wait, rate_limiter):
    try:
        cookies = login_with_retry(driver, wait, rate_limiter)
        return cookies
    except Exception as e:
        logging.error(f"Failed to log in after 3 attempts: {str(e)}")
        raise

def add_product_to_cart(driver, wait, product_element, rate_limiter):
    """Handle the process of adding a single product to cart"""
    try:
        rate_limiter.wait_if_needed()
        
        # Get product name for logging
        product_name = product_element.find_element(By.CSS_SELECTOR, ".product-name").text
        logging.info(f"Processing product: {product_name}")
        
        # First dropdown selections
        dropdown1 = Select(product_element.find_element(By.CSS_SELECTOR, "select#dropdown1_id"))
        add_random_delay(0.5, 1)
        dropdown1.select_by_index(1)
        
        dropdown2 = Select(product_element.find_element(By.CSS_SELECTOR, "select#dropdown2_id"))
        add_random_delay(0.5, 1)
        dropdown2.select_by_index(1)
        
        add_random_delay(1, 2)
        add_to_cart = product_element.find_element(By.CSS_SELECTOR, "button.add-to-cart")
        add_to_cart.click()
        
        # Handle modal form
        form_modal = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, ".modal-form")))
        add_random_delay(1, 2)
        
        modal_dropdown1 = Select(form_modal.find_element(By.CSS_SELECTOR, "select#modal_dropdown1_id"))
        add_random_delay(0.5, 1)
        modal_dropdown1.select_by_index(1)
        
        modal_dropdown2 = Select(form_modal.find_element(By.CSS_SELECTOR, "select#modal_dropdown2_id"))
        add_random_delay(0.5, 1)
        modal_dropdown2.select_by_index(1)
        
        add_random_delay(1, 2)
        submit_button = form_modal.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()
        
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".success-message")))
        logging.info(f"Successfully added {product_name} to cart")
        add_random_delay(2, 4)
        
    except Exception as e:
        logging.error(f"Failed to add product to cart: {str(e)}")
        take_error_screenshot(driver, 'add_to_cart_failed')
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
                take_error_screenshot(driver, f'product_timeout_page_{page}')
                
                # Try to refresh the page and wait again
                driver.refresh()
                try:
                    product_area = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product_area")))
                except TimeoutException:
                    logging.error(f"Failed to load product area on page {page} after refresh")
                    take_error_screenshot(driver, f'product_timeout_after_refresh_page_{page}')
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





def apply_cookies(driver, cookies):
    """Apply saved cookies to a new browser session"""
    if not cookies:
        logging.error("No cookies provided to apply_cookies")
        return False
        
    try:
        for cookie in cookies:
            driver.add_cookie(cookie)
        logging.info("Applied saved cookies to browser session")
        # Refresh the page to activate cookies
        driver.refresh()
        add_random_delay(1, 2)
        
        # Verify login status (you might need to adjust this based on your site)
        if "login" in driver.current_url.lower():
            logging.warning("Still on login page after applying cookies")
            return False
            
        return True
    except Exception as e:
        logging.warning(f"Failed to apply cookies: {str(e)}")
        return False
