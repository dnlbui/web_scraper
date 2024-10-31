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
