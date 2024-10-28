from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from common.rate_limiter import RateLimiter
from site2_scraper.browser_actions import collect_product_links
from site2_scraper import config
import logging
from site2_scraper.browser_actions import login, navigate_to_sorted_products

def test_collect_product_links():
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    rate_limiter = RateLimiter(max_requests=config.MAX_REQUESTS, time_window=config.TIME_WINDOW)

    try:
        # Login first
        login(driver, wait, rate_limiter)
        
        # Navigate to the sorted products page
        navigate_to_sorted_products(driver, wait, rate_limiter)
        
        # Now collect product links
        all_product_links = collect_product_links(driver, wait, rate_limiter)

        assert len(all_product_links) > 0, "No product links were collected"
        for product in all_product_links:
            assert 'url' in product, "Product info is missing URL"
            assert 'name' in product, "Product info is missing name"
            assert product['url'].startswith('http'), "Invalid product URL"
            assert len(product['name']) > 0, "Product name is empty"

        logging.info(f"Collected a total of {len(all_product_links)} product links")
        logging.info("Product link collection test completed successfully")

    except Exception as e:
        logging.error(f"Product link collection test failed: {str(e)}")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_collect_product_links()
