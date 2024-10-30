import pandas as pd

# Read the CSV file
df = pd.read_csv('PetPharmPricing.csv')

# Remove duplicates based on specified columns
df_cleaned = df.drop_duplicates(
    subset=['Product Name', 'Strength', 'Bottle Size', 'Quantity'],
    keep='first'
)

# Save the cleaned data back to CSV
# Keep all columns and don't write the index
df_cleaned.to_csv('PetPharmPricing_cleaned.csv', index=False)

# Print some statistics
print(f"Original number of rows: {len(df)}")
print(f"Number of rows after removing duplicates: {len(df_cleaned)}")
print(f"Number of duplicates removed: {len(df) - len(df_cleaned)}")