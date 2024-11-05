Here's a markmap of the site3_scraper's flow:

# Site3 Scraper Flow

## 1. Entry Point (main.py)
- ### Command Line Arguments
  - --input-file: JSON file with URLs
  - --show-progress: Display processing status
  - --collect-urls: Gather URLs from website
- ### Initial Setup
  
```17:25:site3_scraper/main.py
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('price_scraper.log'),
            logging.StreamHandler()
        ]
    )
```

  - Configure logging
  - Initialize database
  - Setup rate limiter

## 2. Authentication Flow
- ### Login Process
  
```19:64:site3_scraper/browser_actions.py
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
```

  - Attempt login with retry logic
  - Human-like typing simulation
  - Cookie capture
  - Error screenshot on failure

## 3. URL Collection
- ### Two Sources
  - From input JSON file
  - From site2_scraper database
    
```167:195:site3_scraper/database.py
    def get_urls_from_site2_db(self):
        """Get product URLs from site2_scraper database"""
        try:
            # Get the path to the web_scraper directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            web_scraper_dir = os.path.dirname(os.path.dirname(current_dir))
            db_path = os.path.join(web_scraper_dir, 'web_scraper', 'site2_scraper.db')
            
            if not os.path.exists(db_path):
                logging.error(f"Database file not found at: {db_path}")
                return []

            logging.info(f"Attempting to connect to database at: {db_path}")
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                # Enable foreign keys
                cursor.execute('PRAGMA foreign_keys = ON')
                cursor.execute('SELECT url, name FROM product_links')
                results = cursor.fetchall()
                for url, name in results:
                    logging.info(f"Found product in DB: {name} - {url}")
                urls = [row[0] for row in results]
                logging.info(f"Loaded {len(urls)} URLs from site2_scraper database")
                return urls
        except Exception as e:
            logging.error(f"Error loading URLs from site2_scraper database: {str(e)}")
            logging.error(f"Current directory: {current_dir}")
            logging.error(f"Web scraper directory: {web_scraper_dir}")
            return []
```

  - From website (if --collect-urls flag)
    
```99:143:site3_scraper/browser_actions.py
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
```


## 4. Product Processing
- ### Batch Processing
  - Groups URLs into batches of 10
  - Uses ThreadPoolExecutor (20 workers)
  
```128:142:site3_scraper/main.py
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
```


- ### Single Product Processing
  
```24:90:site3_scraper/data_processing.py
def process_single_product(driver, wait, url):
    """Process a single product page and extract all relevant information"""
    try:
        logging.info(f"Processing URL: {url}")
        driver.get(url)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Extract product name from URL
        product_name = get_product_name_from_url(url)
        logging.info(f"Product name: {product_name}")

        # Extract variations first
        try:
            variations = extract_variations_data(driver)
        except Exception as e:
            logging.error(f"Error extracting variations for {url}: {str(e)}")
            variations = []
        
        # Extract price information
        try:
            price_script = extract_price_script(driver, wait)
            price_info = parse_javascript_price(price_script) if price_script else None
        except Exception as e:
            logging.error(f"Error extracting price info for {url}: {str(e)}")
            price_info = None

        # If we don't have valid price data, return None
        if not price_info and not variations:
            logging.warning(f"No valid price data or variations found for {url}")
            return None

        # If we have variations but no price_info, use first variation's price
        if variations and not price_info:
            price_info = {
                'base_price': variations[0]['display_price'],
                'dispensary_fee': 0,
                'currency': '$'
            }

        # If we have price_info but no variations, create a simple variation
        if price_info and not variations:
            variations = [{
                'variation_id': '0',
                'display_price': price_info['base_price'],
                'display_regular_price': price_info['base_price'],
                'is_in_stock': True,
                'attributes': {
                    'attribute_pa_strength': '',
                    'attribute_pa_bottle-size': ''
                },
                'sku': ''
            }]

        product_data = {
            'url': url,
            'name': product_name,
            'price_info': price_info,
            'variations': variations,
            'timestamp': datetime.now().isoformat()
        }

        return product_data

    except Exception as e:
        logging.error(f"Error processing product {url}: {str(e)}")
        logging.error(f"Stack trace:", exc_info=True)
        return None
```

  - Extract product name
  - Get variations data
  - Extract price information
  - Parse JavaScript price data

## 5. Data Extraction
- ### Price Extraction
  - JavaScript price parsing
  
```95:129:site3_scraper/utils.py
def parse_javascript_price(script_content):
    """Parse price information from JavaScript code block"""
    try:
        # Try original format first
        price_match = re.search(r'price\s*=\s*([\d.]+)', script_content)
        if not price_match:
            # Try alternate format with var declaration
            price_match = re.search(r'var\s+price\s*=\s*([\d.]+),', script_content)
        base_price = float(price_match.group(1)) if price_match else None

        # Try original format first for dispensary fee
        fee_match = re.search(r'dispensary_fee\s*=\s*[\'"]?([\d.]+)', script_content)
        if not fee_match:
            # Try alternate format with var declaration
            fee_match = re.search(r'var\s+dispensary_fee\s*=\s*[\'"]?([\d.]+)', script_content)
        dispensary_fee = float(fee_match.group(1)) if fee_match else None

        # Try original format first for currency
        currency_match = re.search(r'currency\s*=\s*[\'"](.+?)[\'"]', script_content)
        if not currency_match:
            # Try alternate format with var declaration
            currency_match = re.search(r'var\s+currency\s*=\s*[\'"](.+?)[\'"]', script_content)
        currency = currency_match.group(1) if currency_match else '$'

        if base_price is not None:
            return {
                'base_price': base_price,
                'dispensary_fee': dispensary_fee if dispensary_fee is not None else 0,
                'currency': currency
            }
        return None
    except Exception as e:
        logging.error(f"Error parsing JavaScript price: {str(e)}")
        return None
```

  - Price normalization
  
```22:35:site3_scraper/utils.py
def normalize_price(price_str):
    """Normalize price string to float"""
    try:
        # Remove currency symbols and whitespace
        cleaned = re.sub(r'[^\d.,]', '', price_str)
        # Handle different decimal separators
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
        return float(cleaned)
    except (ValueError, TypeError) as e:
        logging.error(f"Error normalizing price {price_str}: {str(e)}")
        return None
```


- ### Variation Handling
  
```92:125:site3_scraper/data_processing.py
def extract_variations_data(driver):
    """Extract product variations data from the page"""
    try:
        # First check if there's a variations form
        variations_form = driver.find_elements(By.CLASS_NAME, "variations_form")
        
        if variations_form:
            variations_data = variations_form[0].get_attribute('data-product_variations')
            if variations_data:
                return json.loads(html.unescape(variations_data))
        
        # If no variations form found, check for simple product
        quantity_input = driver.find_elements(By.CLASS_NAME, "qty")
        if quantity_input:
            price_data = get_simple_product_price(driver)
            if price_data:
                # Create a simple variation structure for products with just quantity
                simple_variation = [{
                    'variation_id': 0,
                    'display_price': price_data['display_price'],
                    'display_regular_price': price_data['display_regular_price'],
                    'is_in_stock': True,
                    'attributes': {
                        'attribute_pa_strength': '',
                        'attribute_pa_bottle-size': ''
                    },
                    'sku': get_product_sku(driver) or ''
                }]
                return simple_variation
            
        return []
    except Exception as e:
        logging.error(f"Error extracting variations data: {str(e)}")
        return []
```

  - Extract variation forms
  - Handle simple products
  - Process multiple variations

## 6. Data Storage
- ### Database Operations
  
```61:113:site3_scraper/database.py
    def save_product_price(self, product_data):
        """Save complete product data including variations"""
        logging.info(f"Saving product data for: {product_data['url']}")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('BEGIN TRANSACTION')
                
                # Insert into product_prices table
                cursor.execute('''
                    INSERT INTO product_prices 
                    (url, name, base_price, dispensary_fee, currency, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    product_data['url'],
                    product_data['name'],
                    product_data['price_info']['base_price'],
                    product_data['price_info']['dispensary_fee'],
                    product_data['price_info']['currency'],
                    product_data['timestamp']
                ))
                
                product_id = cursor.lastrowid
                
                # Insert variation data if present
                if 'variations' in product_data and product_data['variations']:
                    for variation in product_data['variations']:
                        cursor.execute('''
                            INSERT INTO variations 
                            (product_id, product_name, variation_id, strength, bottle_size,
                             display_price, regular_price, sku, is_in_stock)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            product_id,
                            product_data['name'],
                            str(variation['variation_id']),
                            variation['attributes'].get('attribute_pa_strength', ''),
                            variation['attributes'].get('attribute_pa_bottle-size', ''),
                            float(variation['display_price']),
                            float(variation['display_regular_price']),
                            variation.get('sku', ''),
                            1 if variation['is_in_stock'] else 0
                        ))
                conn.commit()
                logging.info(f"Successfully saved product data for: {product_data['url']}")
                
            except Exception as e:
                conn.rollback()
                logging.error(f"Error saving product data for {product_data['url']}: {str(e)}")
                logging.error("Stack trace:", exc_info=True)
                raise
```

  - Save product prices
  - Store variations
  - Transaction management
  - Error handling

## 7. Output Generation
- ### Final Results
  - Export to JSON file
  
```149:154:site3_scraper/main.py
    # Export results to JSON
    results = db.get_all_results()
    with open('price_data.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logging.info("Price scraper finished. Results saved to price_data.json")
```

  - Logging statistics
    - Total URLs processed
    - Success count
    - Failure count

## 8. Error Handling
- ### Screenshot Capture
  
```8:20:site3_scraper/utils.py
def take_error_screenshot(driver, error_name):
    """Take a screenshot when an error occurs"""
    try:
        screenshots_dir = 'error_screenshots'
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{screenshots_dir}/{error_name}_{timestamp}.png"
        driver.save_screenshot(filename)
        logging.info(f"Error screenshot saved: {filename}")
    except Exception as e:
        logging.error(f"Failed to take error screenshot: {str(e)}")
```

- ### Logging
  - File logging
  - Console output
  - Error tracking
- ### Retry Logic
  - Login attempts
  - Rate limiting
  
```11:13:site3_scraper/config.py
# Rate limiter configuration
MAX_REQUESTS = 20
TIME_WINDOW = 60
```
