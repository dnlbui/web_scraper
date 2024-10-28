import json
import csv

def extract_info(name_str):
    # Initialize default values
    info = {
        'base_name': '',
        'pet_name': '',
        'strength': '',
        'flavor': '',
        'bottle_size': ''
    }
    
    # Split the name string into lines
    lines = name_str.split('\n')
    
    # First line is always the base name
    info['base_name'] = lines[0]
    
    # Process remaining lines
    for line in lines[1:]:
        line = line.strip()
        if line.startswith('Pet Name:'):
            info['pet_name'] = line.replace('Pet Name:', '').strip()
        elif line.startswith('Strength:'):
            info['strength'] = line.replace('Strength:', '').strip()
        elif line.startswith('Flavor:'):
            info['flavor'] = line.replace('Flavor:', '').strip()
        elif line.startswith('Bottle Size:'):
            info['bottle_size'] = line.replace('Bottle Size:', '').strip()
        # Handle cases where fields don't have labels
        elif line and ':' not in line:
            if not info['strength'] and any(unit in line.lower() for unit in ['mg', 'mcg', '%', 'units']):
                info['strength'] = line.strip()
            elif not info['flavor'] and any(flavor in line.lower() for flavor in ['chicken', 'beef', 'fish', 'tuna', 'bacon', 'catnip', 'banana', 'cherry', 'apple', 'peanut butter']):
                info['flavor'] = line.strip()
            elif not info['bottle_size'] and any(unit in line.lower() for unit in ['ml', 'oz', 'tablets', 'capsules']):
                info['bottle_size'] = line.strip()
    
    return info

def convert_json_to_csv(json_file, csv_file):
    # Read JSON file
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Open CSV file for writing
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow([
            'Product Name',
            'Pet Name',
            'Strength',
            'Flavor',
            'Bottle Size',
            'Price',
            'Quantity'
        ])
        
        # Process each item
        for item in data:
            # Extract information from the name field
            info = extract_info(item['name'])
            
            # Clean up price (remove '$' and convert to float)
            price = float(item['price'].replace('$', '').replace(',', ''))
            
            # Write row
            writer.writerow([
                info['base_name'],
                info['pet_name'],
                info['strength'],
                info['flavor'],
                info['bottle_size'],
                price,
                item['quantity']
            ])

# Run the conversion
convert_json_to_csv('cart_contents.json', 'cart_contents.csv')
