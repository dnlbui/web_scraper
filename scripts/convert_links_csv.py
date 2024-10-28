import json
import csv

def convert_links_to_csv(json_file, csv_file):
    # Read JSON file
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Open CSV file for writing
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(['Product Name', 'URL'])
        
        # Write each product
        for item in data:
            writer.writerow([
                item['name'],
                item['url']
            ])

# Run the conversion
convert_links_to_csv('product_links.json', 'product_links.csv')