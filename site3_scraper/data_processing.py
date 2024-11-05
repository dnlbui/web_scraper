import logging
import re
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
import json
import html

from site3_scraper.browser_actions import extract_price_script
from site3_scraper.utils import parse_javascript_price

def get_product_name_from_url(url):
    """Extract and format product name from URL"""
    # Get the last part of the URL before any query parameters
    product_slug = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
    # Remove any query parameters if present
    product_slug = product_slug.split('?')[0]
    # Replace hyphens with spaces and capitalize words
    product_name = product_slug.replace('-', ' ').title()
    return product_name

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

def get_simple_product_price(driver):
    """Extract price for simple products"""
    try:
        # Try to get price from JavaScript first
        script = driver.execute_script("""
            return {
                price: typeof price !== 'undefined' && price !== '' ? parseFloat(price) : null,
                dispensary_fee: typeof dispensary_fee !== 'undefined' && dispensary_fee !== '' ? parseFloat(dispensary_fee) : null
            }
        """)
        
        if script and script['price'] is not None:
            base_price = script['price']
            dispensary_fee = script['dispensary_fee'] if script['dispensary_fee'] is not None else 0
            total_price = base_price + dispensary_fee
            
            return {
                'display_price': total_price,
                'display_regular_price': total_price,
                'base_price': base_price,
                'dispensary_fee': dispensary_fee
            }
            
        # Fallback to looking for price element
        price_element = driver.find_element(By.CLASS_NAME, "price")
        if price_element and price_element.text.strip():
            price_text = price_element.text.strip()
            if price_text and price_text != '':
                price = float(price_text.replace('$', '').strip())
                return {
                    'display_price': price,
                    'display_regular_price': price,
                    'base_price': price,
                    'dispensary_fee': 0
                }
            
        logging.warning(f"No valid price found for product")
        return None
    except Exception as e:
        logging.error(f"Error extracting simple product price: {str(e)}")
        return None

def get_product_sku(driver):
    """Extract SKU for simple products"""
    try:
        sku_element = driver.find_element(By.CLASS_NAME, "sku")
        if sku_element:
            return sku_element.text.strip()
        return None
    except:
        return None