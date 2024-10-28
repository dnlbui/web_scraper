# Site2 Scraper

A Python-based web scraper for automating product collection and cart management.

## Prerequisites

- Python 3.7+
- Chrome browser installed
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd site2-scraper```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate # On Windows use: venv\Scripts\activate```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with your credentials:
```bash
SITE2_USERNAME=<your-username>
SITE2_PASSWORD=<your-password>
```

## Usage

### Basic Run
To run the scraper with default settings:
```bash
python -m site2_scraper.main
```

### Run with Failed Products
To run the scraper using the failed products list:
```bash
python -m site2_scraper.main --use-warnings
```


## Configuration

You can modify the following settings in `site2_scraper/config.py`:
- `MAX_PAGES`: Maximum number of pages to scrape (default: 37)
- `MAX_WORKERS`: Maximum number of concurrent workers (default: 10)
- `MAX_REQUESTS`: Maximum requests per time window (default: 20)
- `TIME_WINDOW`: Time window in seconds for rate limiting (default: 60)
- `DEFAULT_QUANTITY`: Default quantity for each product (default: 30)

## Output Files

- `cart_contents.json`: Contains all successfully processed cart items
- `cart_scraper.log`: Detailed logging information
- `product_links.json`: Collected product links
- `failed_products.json`: Products that failed to process

## Troubleshooting

If you encounter any issues:
1. Check the `cart_scraper.log` file for detailed error messages
2. Ensure your `.env` file contains valid credentials
3. Verify your Chrome browser is up to date
4. Check your internet connection

## Rate Limiting

The scraper includes built-in rate limiting to prevent overwhelming the target site:
- 20 requests per minute by default
- Random delays between actions
- Concurrent processing limited to 10 workers by default