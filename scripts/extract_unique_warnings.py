import re

def extract_unique_warnings(log_file, output_file):
    # Set to store unique URLs
    unique_urls = set()
    # Dict to store the full warning message for each unique URL
    url_warnings = {}
    
    # Pattern to match URLs
    url_pattern = re.compile(r'URL: (https://[^\)]+)')
    
    # Read log file and collect unique URLs with their warnings
    with open(log_file, 'r') as input_file:  # Changed from line_file to input_file
        for line in input_file:  # Fixed variable name here
            if 'Failed to add product to cart:' in line:
                match = url_pattern.search(line)
                if match:
                    url = match.group(1)
                    if url not in unique_urls:
                        unique_urls.add(url)
                        url_warnings[url] = line
    
    # Write unique warnings to output file
    with open(output_file, 'w') as output:
        for url in unique_urls:
            output.write(url_warnings[url])

# Run the extraction
extract_unique_warnings('warnings.log', 'unique_warnings.log')