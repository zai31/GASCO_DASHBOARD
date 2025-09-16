import pandas as pd
from datetime import datetime
import os

# Compressor data to populate
compressors_data = {
    'A': {'current_hrs': 500},
    'B': {'current_hrs': 79300},
    'C': {'current_hrs': 76900}
}

# Create DataFrame
data = []
for comp_id, comp_info in compressors_data.items():
    data.append({
        'Compressor ID': comp_id,
        'Compressor Name': f'Compressor {comp_id}',
        'Current Hours': comp_info['current_hrs'],
        'Date Updated': datetime.now().date(),
        'Status': 'Active',
        'Notes': 'Initial setup from maintenance module'
    })

df = pd.DataFrame(data)

# Ensure Data directory exists
os.makedirs('Data', exist_ok=True)

# Save to Excel
df.to_excel('Data/Compressor_Data.xlsx', index=False, engine='openpyxl')

print("✅ Compressor data has been populated in Data/Compressor_Data.xlsx")
print(f"Created {len(data)} compressor records:")
for _, row in df.iterrows():
    print(f"  - {row['Compressor Name']}: {row['Current Hours']:,} hours")
