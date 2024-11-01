import logging
import os
from datetime import datetime

def take_error_screenshot(driver, error_type):
    """Take a screenshot when an error occurs
    
    Args:
        driver: Selenium WebDriver instance
        error_type: String describing the error (e.g. 'login_failed', 'cart_error')
    
    Returns:
        str: Path to the screenshot file or None if screenshot failed
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        screenshots_dir = 'error_screenshots'
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)
            
        filename = f"{error_type}_{timestamp}.png"
        filepath = os.path.join(screenshots_dir, filename)
        driver.save_screenshot(filepath)
        logging.info(f"Error screenshot saved: {filepath}")
        return filepath
    except Exception as e:
        logging.warning(f"Failed to take error screenshot: {str(e)}")
        return None

def normalize_product_name(name):
    """Normalize product name and extract additional details"""
    details = {
        'name': '',
        'strength': '',
        'bottle_size': ''
    }
    
    lines = [line.strip() for line in name.split('\n') if line.strip()]
    
    # First line is always the base product name
    if lines:
        details['name'] = lines[0]
    
    # Look for strength and bottle size in remaining lines
    for line in lines:
        if line.startswith('Strength:'):
            details['strength'] = line.replace('Strength:', '').strip()
        elif line.startswith('Bottle Size:'):
            details['bottle_size'] = line.replace('Bottle Size:', '').strip()
            
    return details