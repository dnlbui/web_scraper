I'll help you update the README.md to include information about resuming progress and checking status. Here's the modified version:

```markdown
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
cd site2-scraper
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate # On Windows use: venv\Scripts\activate
```

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

### Check Processing Status
To view the current progress and status:
```bash
python -m site2_scraper.main --show-progress
```

### Resuming Progress
The scraper automatically tracks progress in the database. If interrupted:
1. The current progress is saved
2. Any 'processing' items are reset to 'pending'
3. When restarted, it will continue from where it left off

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
- `site2_scraper.db`: SQLite database containing processing status and results

## Database Tables

- `processing_status`: Tracks the progress of each product
- `cart_contents`: Successfully added cart items
- `product_links`: All collected product links
- `failed_products`: Products that failed to process
- `out_of_stock_products`: Products marked as out of stock

## Troubleshooting

If you encounter any issues:
1. Check the `cart_scraper.log` file for detailed error messages
2. Use `--show-progress` to view current processing status
3. Ensure your `.env` file contains valid credentials
4. Verify your Chrome browser is up to date
5. Check your internet connection

## Rate Limiting

The scraper includes built-in rate limiting to prevent overwhelming the target site:
- 20 requests per minute by default
- Random delays between actions
- Concurrent processing limited to 10 workers by default

## Interrupting and Resuming

To safely stop the scraper:
1. Press Ctrl+C once to initiate graceful shutdown
2. Wait for current operations to complete
3. Progress will be saved automatically
4. Restart using the same command to resume from last position
```

This updated README reflects the changes we discussed, particularly around progress tracking and resuming functionality. The original README can be found at:


````1:78:site2_scraper/README.md
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
````
