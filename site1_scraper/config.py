# Scraper configuration
MAX_PAGES = 10
MAX_WORKERS = 6

# Rate limiter configuration
MAX_REQUESTS = 30
TIME_WINDOW = 60

# Base URL for scraping
BASE_URL = "https://nexgenvetrx.com/search.php?page={}&section=product&search_query=inject"

# Output file name
OUTPUT_FILE = "injectables_with_details.csv"