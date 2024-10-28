import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Scraper configuration
MAX_PAGES = 37
MAX_WORKERS = 3 # might be max at 3

# Rate limiter configuration
MAX_REQUESTS = 20
TIME_WINDOW = 60

# URLs
LOGIN_URL = "https://www.svpmeds.com/login/"
PRODUCTS_PAGE_URL = "https://www.svpmeds.com/product-category/prescription-medicines/?orderby=popularity"
CART_URL = "https://www.svpmeds.com/cart-2/"

# Login credentials
SITE2_USERNAME = os.getenv("SITE2_USERNAME")
SITE2_PASSWORD = os.getenv("SITE2_PASSWORD")

# Output file name
OUTPUT_FILE = "cart_contents.csv"

# Product configuration
DEFAULT_QUANTITY = 30  # Default quantity for each product
