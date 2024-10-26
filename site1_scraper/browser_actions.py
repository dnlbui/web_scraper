import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import config

def collect_product_links(driver, wait, rate_limiter):
    all_links = []
    page = 1
    
    while page <= config.MAX_PAGES:
        url = config.BASE_URL.format(page)
        logging.info(f"\n{'='*50}\nProcessing search page {page}: {url}")
        driver.get(url)
        rate_limiter.wait_if_needed()
        
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
