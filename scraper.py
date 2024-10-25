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
    
    while page <= 6:
        url = base_url.format(page)
        driver.get(url)
        time.sleep(2)
        
        containers = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article.product-item-container")))
        
        page_links = []
        for container in containers:
            try:
                link_element = container.find_element(By.CSS_SELECTOR, "h4.card-title a")
                page_links.append({
                    'url': link_element.get_attribute('href'),
                    'name': link_element.text.strip(),
                    'description': container.find_element(By.CSS_SELECTOR, "div.description").text.strip()
                })
            except Exception as e:
                logging.error(f"Error collecting link on page {page}: {e}")
                continue
        
        all_links.extend(page_links)
        logging.info(f"Collected {len(page_links)} links from page {page}")
        page += 1
    
    return all_links

def process_single_product(product_info):
    """Process a single product in its own browser instance"""
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        driver.get(product_info['url'])
        time.sleep(2)
        
        info_dl = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".productView-info-dl")))
        details = {
            'Product Name': product_info['name'],
            'URL': product_info['url'],
            'Description': product_info['description']
        }
        
        # Get specifications
        dt_elements = info_dl.find_elements(By.TAG_NAME, "dt")
        dd_elements = info_dl.find_elements(By.TAG_NAME, "dd")
        
        for dt, dd in zip(dt_elements, dd_elements):
            key = dt.text.strip(':')
            value = dd.text.strip()
            details[key] = value
            
        logging.info(f"Successfully processed: {product_info['name']}")
        return details
        
    except Exception as e:
        logging.error(f"Error processing {product_info['name']}: {e}")
        return None
    finally:
        driver.quit()

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Initial driver to collect all links
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        # First collect all product links
        all_product_links = collect_product_links(driver, wait)
        logging.info(f"Collected total of {len(all_product_links)} product links")
    finally:
        driver.quit()
    
    # Process products in parallel
    all_products = []
    with ThreadPoolExecutor(max_workers=5) as executor:  # Process 5 products simultaneously
        future_to_product = {executor.submit(process_single_product, product): product 
                           for product in all_product_links}
        
        for future in future_to_product:
            result = future.result()
            if result:
                all_products.append(result)
    
    # Save to CSV
    if all_products:
        fieldnames = set()
        for product in all_products:
            fieldnames.update(product.keys())
        
        try:
            with open("injectables_with_details.csv", "w", newline="", encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=list(fieldnames))
                writer.writeheader()
                for product in all_products:
                    writer.writerow(product)
                logging.info("Data successfully written to injectables_with_details.csv")
        except Exception as e:
            logging.error(f"Failed to write to CSV file: {e}")
    
    print(f"\nTotal products processed: {len(all_products)}")

if __name__ == "__main__":
    main()