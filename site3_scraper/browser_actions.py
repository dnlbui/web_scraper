import time
import logging
import random
import json
import os
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from site3_scraper import config
from site3_scraper.utils import take_error_screenshot
from site3_scraper.database import Database

def add_random_delay(min_seconds=1, max_seconds=3):
    """Add a random delay between actions"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def login_with_retry(driver, wait, rate_limiter, max_attempts=3):
    """Attempt to login with retry logic"""
    for attempt in range(max_attempts):
        try:
            logging.info(f"Login attempt {attempt + 1} of {max_attempts}")
            driver.get(config.LOGIN_URL)
            rate_limiter.delay()
            
            # Wait for login form with longer timeout on first attempt
            timeout = 20 if attempt == 0 else 10
            username_input = wait.until(EC.presence_of_element_located(
                (By.ID, "username")), timeout)
            password_input = driver.find_element(By.ID, "passwordl")
            
            # Enter credentials with human-like typing
            for char in config.SITE2_USERNAME:
                username_input.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            
            for char in config.SITE2_PASSWORD:
                password_input.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            
            # Add a small delay before clicking
            time.sleep(random.uniform(1, 2))
            login_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Login']")
            login_button.click()
            
            # Wait for successful login
            wait.until(EC.url_changes(config.LOGIN_URL))
            
            if "login" in driver.current_url.lower():
                raise Exception("Still on login page after attempt")
                
            cookies = driver.get_cookies()
            logging.info("Login successful")
            return cookies
            
        except Exception as e:
            logging.error(f"Login attempt {attempt + 1} failed: {str(e)}")
            take_error_screenshot(driver, f'login_failed_attempt_{attempt + 1}')
            if attempt < max_attempts - 1:
                time.sleep(5)  # Wait before retry
            continue
            
    return None

def login(driver, wait, rate_limiter):
    """Main login function with retry logic"""
    try:
        cookies = login_with_retry(driver, wait, rate_limiter)
        return cookies
    except Exception as e:
        logging.error(f"Failed to log in after all attempts: {str(e)}")
        return None

def extract_price_script(driver, wait):
    """Extract the JavaScript code block containing price information"""
    try:
        scripts = driver.find_elements(By.TAG_NAME, "script")
        price_script = None
        
        for script in scripts:
            content = script.get_attribute('innerHTML')
            # Check for both formats of price declaration
            if ('dispensary_fee' in content and 
                ('price =' in content or 'var price =' in content)):
                price_script = content
                break
                
        if not price_script:
            logging.warning("Price script not found")
            return None
            
        return price_script
        
    except Exception as e:
        logging.error(f"Error extracting price script: {str(e)}")
        return None

def collect_product_links(driver, wait, rate_limiter):
    """Collect all product links from the product listing pages"""
    db = Database()
    all_product_links = []
    page = 1
    
    try:
        while True:
            # Navigate to the current page
            url = f"{config.PRODUCT_LIST_URL}page/{page}/"
            driver.get(url)
            rate_limiter.delay()
            
            # Wait for product grid to load
            products = wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, '.product-grid .product-link')))
            
            if not products:
                break
                
            # Extract links
            page_links = [product.get_attribute('href') for product in products]
            all_product_links.extend(page_links)
            
            # Store links in database
            for link in page_links:
                db.insert_product_url(link)
            
            # Check for next page
            try:
                next_page = driver.find_element(By.CSS_SELECTOR, '.next.page-numbers')
                if not next_page.is_displayed():
                    break
            except NoSuchElementException:
                break
                
            page += 1
            
        logging.info(f"Collected {len(all_product_links)} product links")
        return all_product_links
        
    except Exception as e:
        logging.error(f"Error collecting product links: {str(e)}")
        take_error_screenshot(driver, 'product_links_failed')
        return all_product_links

def apply_cookies(driver, cookies):
    """Apply saved cookies to browser session"""
    if not cookies:
        logging.warning("No cookies provided to apply")
        return False
        
    try:
        # Navigate to the domain first
        driver.get(config.BASE_URL)
        time.sleep(2)  # Wait for page to load
        
        # Clean and apply cookies
        for cookie in cookies:
            try:
                # Clean cookie data
                clean_cookie = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie.get('domain', '.svpmeds.com'),  # Use existing domain or default
                    'path': '/'
                }
                driver.add_cookie(clean_cookie)
            except Exception as e:
                logging.warning(f"Failed to add cookie {cookie.get('name')}: {str(e)}")
                continue
        
        # Navigate to a protected page to verify login
        driver.get(config.PRODUCTS_PAGE_URL)
        time.sleep(2)
        
        # Check if we're redirected to login
        if "login" in driver.current_url.lower():
            logging.error("Cookie authentication failed")
            return False
            
        logging.info("Successfully applied cookies and verified login")
        return True
        
    except Exception as e:
        logging.error(f"Error applying cookies: {str(e)}")
        return False

def get_current_price(driver, wait):
    """Get the current displayed price for selected variations"""
    try:
        price_element = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '.single_variation span.amount')))
        price_text = price_element.text.strip()
        return float(price_text.replace('$', '').strip())
    except Exception as e:
        logging.error(f"Error getting current price: {str(e)}")
        return None

def select_variation_and_get_price(driver, wait, variation_type, option):
    """Select a variation option and return the resulting price"""
    try:
        select = Select(driver.find_element(By.ID, variation_type))
        select.select_by_visible_text(option)
        add_random_delay(1, 2)  # Wait for price update
        return get_current_price(driver, wait)
    except Exception as e:
        logging.error(f"Error selecting variation {variation_type} - {option}: {str(e)}")
        return None