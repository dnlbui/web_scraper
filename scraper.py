from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
import time
import csv
import logging
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def collect_product_links(driver, wait):
    """Collect all product links from all pages first"""
    all_links = []
    page = 1
    base_url = "https://nexgenvetrx.com/search.php?page={}&section=product&search_query=inject"
    
    while page <= 1:
        url = base_url.format(page)
        logging.info(f"\n{'='*50}\nProcessing search page {page}: {url}")
        driver.get(url)
        time.sleep(2)
        
        containers = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR, "article.product-item-container")))
        logging.info(f"Found {len(containers)} product containers on page {page}")
        
        page_links = []
        for idx, container in enumerate(containers, 1):
            try:
                link_element = container.find_element(By.CSS_SELECTOR, "h4.card-title a")
                product_data = {
                    'url': link_element.get_attribute('href'),
                    'name': link_element.text.strip()
                }
                page_links.append(product_data)
                logging.info(f"Page {page} - Product {idx}:")
                logging.info(f"  Name: {product_data['name']}")
                logging.info(f"  URL: {product_data['url']}")
            except Exception as e:
                logging.error(f"Error collecting link on page {page}, product {idx}: {str(e)}")
                continue
        
        all_links.extend(page_links)
        logging.info(f"\nCompleted page {page}: Collected {len(page_links)} products")
        page += 1
    
    return all_links

def process_single_product(product_info):
    """Process a single product in its own browser instance"""
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    logging.info(f"\n{'='*50}\nProcessing product: {product_info['name']}")
    logging.info(f"URL: {product_info['url']}")
    
    try:
        driver.get(product_info['url'])
        time.sleep(2)
        
        # Get the full description
        try:
            description_element = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "#tab-description")))
            description = description_element.text.strip()
            logging.info(f"\nDescription found ({len(description)} characters):")
            logging.info(f"{description[:200]}...") # Log first 200 chars
        except Exception as e:
            logging.error(f"Error getting description: {str(e)}")
            description = ""
            
        # Get product details
        info_dl = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".productView-info-dl")))
        details = {
            'name': product_info['name'],
            'url': product_info['url'],
            'description': description
        }
        
        # Log the collected data
        logging.info("\nCollected product details:")
        for key, value in details.items():
            if key == 'description':
                logging.info(f"{key}: {value[:100]}...")  # First 100 chars of description
            else:
                logging.info(f"{key}: {value}")
        
        return details
        
    except Exception as e:
        logging.error(f"Error processing product {product_info['name']}: {str(e)}")
        return None
    finally:
        driver.quit()

def main():
    # Set up logging to both file and console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scraper_debug.log'),
            logging.StreamHandler()
        ]
    )
    
    logging.info("\nStarting web scraper...")
    
    # Initial driver to collect all links
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        # First collect all product links
        all_product_links = collect_product_links(driver, wait)
        logging.info(f"\nCollected total of {len(all_product_links)} product links")
    finally:
        driver.quit()
    
    # Process products in parallel
    all_products = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_product = {executor.submit(process_single_product, product): product 
                           for product in all_product_links}
        
        for future in future_to_product:
            result = future.result()
            if result:
                all_products.append(result)
                logging.info(f"Added product to final list: {result['name']}")
    
    # Save to CSV
    if all_products:
        # Define specific fieldnames in the order we want
        fieldnames = ['name', 'url', 'description']
        
        try:
            filename = "injectables_with_details.csv"
            with open(filename, "w", newline="", encoding='utf-8-sig') as file:  # Note the utf-8-sig encoding
                writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
                writer.writeheader()
                for product in all_products:
                    # Ensure all fields exist in the product dict
                    row = {
                        'name': product.get('name', ''),
                        'url': product.get('url', ''),
                        'description': product.get('description', '')
                    }
                    writer.writerow(row)
                logging.info(f"\nData successfully written to {filename}")
                logging.info(f"Fields saved: {', '.join(fieldnames)}")
        except Exception as e:
            logging.error(f"Failed to write to CSV file: {str(e)}")
    
    logging.info(f"\nScraping completed. Total products processed: {len(all_products)}")

if __name__ == "__main__":
    main()
