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