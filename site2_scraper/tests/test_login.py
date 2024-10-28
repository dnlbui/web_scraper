import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from common.rate_limiter import RateLimiter
from ..browser_actions import login
from .. import config

logging.basicConfig(level=logging.INFO)

def test_login():
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 10)
    rate_limiter = RateLimiter(max_requests=config.MAX_REQUESTS, time_window=config.TIME_WINDOW)

    try:
        login(driver, wait, rate_limiter)
        logging.info("Login test completed successfully")
    except Exception as e:
        logging.error(f"Login test failed: {str(e)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    test_login()