import re
import webbrowser

def extract_urls_from_warnings(log_file):
    urls = []
    url_pattern = re.compile(r'URL: (https://[^\)]+)')
    
    with open(log_file, 'r') as f:
        for line in f:
            if 'Failed to add product to cart:' in line:
                match = url_pattern.search(line)
                if match:
                    urls.append(match.group(1))
    return urls

def open_urls_in_tabs(urls):
    # Open first URL in a new window
    if urls:
        webbrowser.open(urls[0], new=2)  # new=2 opens in a new tab
        
        # Open remaining URLs in new tabs
        for url in urls[1:]:
            webbrowser.open_new_tab(url)

# Run the script
urls = extract_urls_from_warnings('warnings.log')
open_urls_in_tabs(urls)