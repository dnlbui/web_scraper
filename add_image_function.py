import csv

print("Starting CSV modification...")

try:
    # Read the existing CSV and create a new one with modified URLs
    with open('injectables_with_images.csv', 'r', encoding='utf-8') as input_file, \
         open('injectables_with_images_with_function.csv', 'w', newline='', encoding='utf-8') as output_file:
        
        reader = csv.reader(input_file)
        writer = csv.writer(output_file)
        
        # Write header row
        header = next(reader)
        writer.writerow(header)
        
        # Process each row
        row_count = 0
        for row in reader:
            product_name = row[0]
            image_url = row[1]
            # Wrap the URL in the IMAGE function
            image_formula = f'=IMAGE("{image_url}")'
            writer.writerow([product_name, image_formula])
            row_count += 1
        
        print(f"Successfully processed {row_count} rows")
        print(f"New file created: injectables_with_images_with_function.csv")

except FileNotFoundError:
    print("Error: Could not find injectables_with_images.csv in the current directory")
except Exception as e:
    print(f"An error occurred: {str(e)}")

