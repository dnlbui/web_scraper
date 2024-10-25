from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import threading
from urllib.parse import urljoin

def get_all_product_links(driver, wait):
    """Get all product links from all pages at once"""
    all_links = []
    page = 1
    
    while page <= 6:  # Process all 6 pages
        url = f"https://nexgenvetrx.com/search.php?page={page}&section=product&search_query=inject"
        driver.get(url)
        time.sleep(1)
        
        # Get all products on current page
        containers = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article.product-item-container")))
        
        # Extract links and basic info
        for container in containers:
            try:
                link_element = container.find_element(By.CSS_SELECTOR, "h4.card-title a")
                description = container.find_element(By.CSS_SELECTOR, "div.description").text.strip()
                all_links.append({
                    'url': link_element.get_attribute('href'),
                    'name': link_element.text.strip(),
                    'description': description
                })
            except Exception as e:
                logging.error(f"Error getting product link on page {page}: {e}")
                continue
                
        page += 1
        
    logging.info(f"Found {len(all_links)} products total")
    return all_links

def process_product(product_info):
    """Process a single product page"""
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        details = get_product_details(product_info['url'])
        if details:
            details.update({
                'Product Name': product_info['name'],
                'URL': product_info['url'],
                'Description': product_info['description']
            })
            return details
    except Exception as e:
        logging.error(f"Error processing {product_info['name']}: {e}")
    finally:
        driver.quit()
    
    return None

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Initial driver to get all links
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    try:
        # Get all product links first
        all_product_links = get_all_product_links(driver, wait)
    finally:
        driver.quit()
    
    # Process products in parallel
    all_products = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process_product, all_product_links))
        all_products = [p for p in results if p]
    
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