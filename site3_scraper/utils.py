import re
import logging
import os
from datetime import datetime
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

def extract_price_components(price_text):
    """Extract base price and additional fees from price text"""
    try:
        # Remove currency symbols and whitespace
        cleaned = price_text.strip()
        # Look for patterns like "$XX.XX + $Y.YY fee"
        components = cleaned.split('+')
        
        result = {
            'base_price': normalize_price(components[0]),
            'additional_fees': []
        }
        
        if len(components) > 1:
            for component in components[1:]:
                if 'fee' in component.lower():
                    result['additional_fees'].append({
                        'type': 'fee',
                        'amount': normalize_price(component)
                    })
        
        return result
    except Exception as e:
        logging.error(f"Error extracting price components from {price_text}: {str(e)}")
        return None

def normalize_product_name(name):
    """Normalize product name and extract additional details"""
    details = {
        'name': '',
        'strength': '',
        'bottle_size': ''
    }
    
    # Split by newlines and clean up
    lines = [line.strip() for line in name.split('\n') if line.strip()]
    
    # First line is always the base product name
    if lines:
        details['name'] = lines[0]
    
    # Look for strength and bottle size in variations
    for line in lines[1:]:  # Skip the first line since it's the name
        # Common strength patterns
        if any(pattern in line.lower() for pattern in ['mg', 'ml', '%', 'mcg']):
            details['strength'] = line.strip()
        # Common bottle size patterns
        elif any(pattern in line.lower() for pattern in ['ml', 'oz', 'cc']):
            details['bottle_size'] = line.strip()
        # If line contains numbers and units, assume it's either strength or bottle size
        elif any(char.isdigit() for char in line):
            if not details['strength']:
                details['strength'] = line.strip()
            elif not details['bottle_size']:
                details['bottle_size'] = line.strip()
    
    return details

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

def wait_for_price_update(driver, wait, old_price):
    """Wait for price to update after selecting variations"""
    try:
        def price_changed(driver):
            new_price = driver.find_element_by_css_selector('.amount').text
            return normalize_price(new_price) != old_price

        WebDriverWait(driver, 5).until(price_changed)
        return True
    except Exception as e:
        logging.error(f"Error waiting for price update: {str(e)}")
        return False

def format_price_data(price_info):
    """Format price data for consistent output"""
    return {
        'base_price': round(float(price_info['base_price']), 2) if price_info['base_price'] else None,
        'dispensary_fee': round(float(price_info['dispensary_fee']), 2) if price_info['dispensary_fee'] else None,
        'total_price': round(float(price_info['base_price'] or 0) + float(price_info['dispensary_fee'] or 0), 2),
        'currency': price_info['currency']
    }
