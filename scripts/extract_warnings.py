import re

def extract_warnings(log_file, output_file):
    # Pattern to match WARNING lines
    warning_pattern = re.compile(r'.*WARNING.*')
    
    # Read log file and write matching lines to output
    with open(log_file, 'r') as input_file, open(output_file, 'w') as output:
        for line in input_file:
            if 'WARNING' in line:
                output.write(line)

# Run the extraction
extract_warnings('cart_scraper.log', 'warnings.log')