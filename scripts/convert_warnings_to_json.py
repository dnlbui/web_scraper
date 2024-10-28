import re
import json

def convert_warnings_to_json(warnings_file, output_file):
    products = []
    url_pattern = re.compile(r'Failed to add product to cart: (.*?) \(URL: (https://[^\)]+)\)')
    
    with open(warnings_file, 'r') as f:
        for line in f:
            match = url_pattern.search(line)
            if match:
                name = match.group(1)
                url = match.group(2)
                products.append({
                    'name': name,
                    'url': url
                })
    
    # Remove duplicates while preserving order
    seen_urls = set()
    unique_products = []
    for product in products:
        if product['url'] not in seen_urls:
            seen_urls.add(product['url'])
            unique_products.append(product)
    
    # Write to JSON file
    with open(output_file, 'w') as f:
        json.dump(unique_products, f, indent=2)
    
    return len(unique_products)

# Run the conversion
count = convert_warnings_to_json('unique_warnings.log', 'failed_products.json')
print(f"Extracted {count} unique products to failed_products.json")