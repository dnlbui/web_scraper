import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Scraper configuration
MAX_PAGES = 37
MAX_WORKERS = 20 # might be max at 3

# Rate limiter configuration
MAX_REQUESTS = 20
TIME_WINDOW = 60

# URLs
LOGIN_URL = os.getenv("SITE2_LOGIN_URL")
PRODUCTS_PAGE_URL = os.getenv("SITE2_PRODUCTS_PAGE_URL")
CART_URL = os.getenv("SITE2_CART_URL")
BASE_URL = os.getenv("SITE2_BASE_URL")

# Login credentials
SITE2_USERNAME = os.getenv("SITE2_USERNAME")
SITE2_PASSWORD = os.getenv("SITE2_PASSWORD")

# Output file name
OUTPUT_FILE = "cart_contents.csv"

