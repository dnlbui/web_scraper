from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv
import logging
import random
from time import sleep
from concurrent.futures import ThreadPoolExecutor
import queue
from threading import Lock

class RateLimiter:
    """Simple rate limiter to control requests"""
    def __init__(self, max_requests=30, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def wait_if_needed(self):
        now = time.time()
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time <= self.time_window]
        
        if len(self.requests) >= self.max_requests:
            sleep_time = self.requests[0] + self.time_window - now
            if sleep_time > 0:
                logging.info(f"Rate limit reached, waiting {sleep_time:.2f} seconds")
                sleep(sleep_time)
            self.requests = self.requests[1:]
        
        self.requests.append(now)

def add_random_delay(min_seconds=2, max_seconds=5):
    """Add a random delay between actions"""
    sleep(random.uniform(min_seconds, max_seconds))

def login(driver, wait, rate_limiter):
    """Handle site login"""
    try:
        rate_limiter.wait_if_needed()
        driver.get("YOUR_LOGIN_URL")
        add_random_delay(2, 4)
        
        username = wait.until(EC.presence_of_element_located((By.ID, "username_field_id")))
        password = driver.find_element(By.ID, "password_field_id")
        
        # Simulate human typing
        for char in "YOUR_USERNAME":
            username.send_keys(char)
            sleep(random.uniform(0.1, 0.3))
        
        for char in "YOUR_PASSWORD":
            password.send_keys(char)
            sleep(random.uniform(0.1, 0.3))
        
        add_random_delay(1, 2)
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".logged-in-indicator")))
        logging.info("Successfully logged in")
        add_random_delay(3, 5)  # Longer delay after login
        
    except Exception as e:
        logging.error(f"Login failed: {str(e)}")
        raise

def navigate_to_sorted_products(driver, wait, rate_limiter):
    """Navigate to product page and sort by popularity"""
    try:
        rate_limiter.wait_if_needed()
        driver.get("PRODUCTS_PAGE_URL")
        add_random_delay()
        
        sort_dropdown = Select(wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "select#sort_selector_id"))))
        sort_dropdown.select_by_value("popularity")
        
        add_random_delay(2, 4)
        logging.info("Successfully sorted products by popularity")
        
    except Exception as e:
        logging.error(f"Failed to sort products: {str(e)}")
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
        raise

def extract_cart_data(driver, wait, rate_limiter):
    """Extract data from the cart page"""
    try:
        rate_limiter.wait_if_needed()
        driver.get("CART_URL")
        add_random_delay(2, 4)
        
        cart_items = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR, ".cart-item")))
        
        cart_data = []
        for item in cart_items:
            item_data = {
                'name': item.find_element(By.CSS_SELECTOR, ".item-name").text,
                'price': item.find_element(By.CSS_SELECTOR, ".item-price").text,
                'quantity': item.find_element(By.CSS_SELECTOR, ".item-quantity").text,
                # Add other fields as needed
            }
            cart_data.append(item_data)
            
        return cart_data
        
    except Exception as e:
        logging.error(f"Failed to extract cart data: {str(e)}")
        return []

class CartManager:
    """Manage cart operations with thread safety"""
    def __init__(self):
        self.lock = Lock()
        self.product_queue = queue.Queue()
        self.processed_products = set()

    def add_product(self, product_data):
        with self.lock:
            if product_data['url'] not in self.processed_products:
                self.product_queue.put(product_data)
                self.processed_products.add(product_data['url'])

def process_single_product(product_info, rate_limiter):
    """Process a single product in its own browser instance"""
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        rate_limiter.wait_if_needed()
        driver.get(product_info['url'])
        add_random_delay(2, 4)
        
        # Get product details and prepare cart data
        product_data = {
            'url': product_info['url'],
            'name': wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, ".product-name"))).text,
            'dropdowns': {}
        }
        
        # First dropdown selections
        dropdown1 = Select(wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "select#dropdown1_id"))))
        dropdown2 = Select(driver.find_element(By.CSS_SELECTOR, "select#dropdown2_id"))
        
        # Store dropdown options for later use
        product_data['dropdowns']['dropdown1'] = dropdown1.options[1].text
        product_data['dropdowns']['dropdown2'] = dropdown2.options[1].text
        
        return product_data
        
    except Exception as e:
        logging.error(f"Error processing product {product_info['url']}: {str(e)}")
        return None
    finally:
        driver.quit()

def add_to_cart_from_queue(cart_manager, rate_limiter):
    """Process products from the queue and add them to cart"""
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        # Login first
        login(driver, wait, rate_limiter)
        
        while True:
            try:
                # Get next product from queue with timeout
                product_data = cart_manager.product_queue.get(timeout=30)
                
                # Navigate to product page
                rate_limiter.wait_if_needed()
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
    
    # Initial driver to collect product URLs
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        # Navigate to products page and collect URLs
        navigate_to_sorted_products(driver, wait, rate_limiter)
        all_product_links = []
        
        page = 1
        while True:
            try:
                products = wait.until(EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR, ".product-container")))
                
                for product in products:
                    link = product.find_element(By.CSS_SELECTOR, "a.product-link")
                    product_info = {
                        'url': link.get_attribute('href'),
                        'name': link.text.strip()
                    }
                    all_product_links.append(product_info)
                
                next_button = driver.find_element(By.CSS_SELECTOR, ".next-page")
                if not next_button.is_enabled():
                    break
                    
                next_button.click()
                page += 1
                add_random_delay(2, 4)
                
            except Exception as e:
                logging.error(f"Error collecting links on page {page}: {str(e)}")
                break
                
    finally:
        driver.quit()
    
    # Process products in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit product processing tasks
        future_to_product = {
            executor.submit(process_single_product, product, rate_limiter): product 
            for product in all_product_links
        }
        
        # Process results and add to queue
        for future in future_to_product:
            result = future.result()
            if result:
                cart_manager.add_product(result)
    
    # Start cart processors
    cart_processors = []
    num_cart_processors = 2  # Adjust based on needs
    
    with ThreadPoolExecutor(max_workers=num_cart_processors) as executor:
        for _ in range(num_cart_processors):
            cart_processors.append(
                executor.submit(add_to_cart_from_queue, cart_manager, rate_limiter)
            )
    
    # Wait for all cart operations to complete
    cart_manager.product_queue.join()
    
    # Extract and save cart data
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        login(driver, wait, rate_limiter)
        cart_data = extract_cart_data(driver, wait, rate_limiter)
        
        if cart_data:
            filename = "cart_contents.csv"
            fieldnames = ['name', 'price', 'quantity']
            
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(cart_data)
                
            logging.info(f"Cart data saved to {filename}")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
