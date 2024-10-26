# Site1 Scraper

This is a web scraper designed to collect product information from a specific website. It uses Selenium for web automation and supports saving data in both CSV and JSON formats.

## Features

- Scrapes product information including name, URL, and description
- Supports multi-threaded scraping for improved performance
- Implements rate limiting to avoid overloading the target website
- Allows saving output in CSV or JSON format
- Option to include full product descriptions or limit their length

## Usage

To run the scraper, use the following command from the project root directory:
```
python -m site1_scraper.main [options]
```

### Options

- `--json`: Save output as JSON instead of CSV
- `--full-description`: Do not limit description length

### Examples

1. For CSV output with limited description (default):
   ```
   python -m site1_scraper.main
   ```

2. For JSON output with limited description:
   ```
   python -m site1_scraper.main --json
   ```

3. For CSV output with full description:
   ```
   python -m site1_scraper.main --full-description
   ```

4. For JSON output with full description:
   ```
   python -m site1_scraper.main --json --full-description
   ```

## Configuration

Scraper settings can be adjusted in the `config.py` file:

- `MAX_PAGES`: Maximum number of pages to scrape
- `MAX_WORKERS`: Maximum number of threads to use for scraping
- `MAX_REQUESTS`: Maximum number of requests per time window
- `TIME_WINDOW`: Time window in seconds for rate limiting
- `BASE_URL`: Base URL for scraping
- `OUTPUT_FILE`: Output file name

## Output

The scraped data will be saved in the project root directory. The default output file is `injectables_with_details.csv` for CSV format, or `injectables_with_details.json` for JSON format.

## Logging

The scraper logs its activity to both the console and a file named `scraper_debug.log` in the project root directory.

## Dependencies

- Python 3.x
- Selenium
- webdriver_manager
- Other dependencies listed in `requirements.txt`

Make sure to install the required dependencies before running the scraper:
```
pip install -r requirements.txt
```

## Disclaimer

This scraper is designed for educational purposes. Always respect the target website's robots.txt file and terms of service when scraping data.