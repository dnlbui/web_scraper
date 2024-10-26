import logging
import csv
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from site1_scraper import config

def process_single_product(product_info, rate_limiter):
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    
    logging.info(f"\n{'='*50}\nProcessing product: {product_info['name']}")
    logging.info(f"URL: {product_info['url']}")
    
    try:
        driver.get(product_info['url'])
        rate_limiter.wait_if_needed()
        
        try:
            description_element = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "#tab-description")))
            description = description_element.text.strip()
            logging.info(f"\nDescription found ({len(description)} characters):")
            logging.info(f"{description[:200]}...") # Log first 200 chars
        except Exception as e:
            logging.error(f"Error getting description: {str(e)}")
            description = ""
            
        info_dl = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".productView-info-dl")))
        details = {
            'name': product_info['name'],
            'url': product_info['url'],
            'description': description
        }
        
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

def save_to_csv(all_products, filename, full_description=False):
    if all_products:
        try:
            fieldnames = ['name', 'url', 'description']
            
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, 
                                    fieldnames=fieldnames,
                                    delimiter=',',
                                    quoting=csv.QUOTE_ALL)
                
                writer.writeheader()
                
                for product in all_products:
                    description = clean_description(product['description'], full_description)
                    cleaned_product = {
                        'name': product['name'].strip(),
                        'url': product['url'].strip(),
                        'description': description
                    }
                    writer.writerow(cleaned_product)
            
            logging.info(f"\nData successfully written to {filename}")
        except Exception as e:
            logging.error(f"Failed to write to CSV file: {str(e)}")

def save_to_json(all_products, filename, full_description=False):
    if all_products:
        try:
            cleaned_products = []
            for product in all_products:
                description = clean_description(product['description'], full_description)
                cleaned_product = {
                    'name': product['name'].strip(),
                    'url': product['url'].strip(),
                    'description': description
                }
                cleaned_products.append(cleaned_product)
            
            with open(filename, 'w', encoding='utf-8') as file:
                json.dump(cleaned_products, file, ensure_ascii=False, indent=2)
            
            logging.info(f"\nData successfully written to {filename}")
        except Exception as e:
            logging.error(f"Failed to write to JSON file: {str(e)}")

def clean_description(description, full_description=False):
    description = (description
        .strip()
        .replace('\n', ' ')
        .replace('\r', ' ')
        .replace('\t', ' ')
        .replace('"', "'"))
    
    description = ' '.join(description.split())
    
    if not full_description and len(description) > 500:
        description = description[:500].rsplit(' ', 1)[0] + "..."
    
    return description
