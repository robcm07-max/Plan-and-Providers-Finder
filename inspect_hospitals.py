from pathlib import Path
import pandas as pd

## import data
root = Path(__file__).resolve().parent
csv_path = root / "data" / "raw" / "hospital_raw.csv"

df = pd.read_csv(csv_path, dtype=str)

## preview data

print("Number of hospitals:", len(df))
print("\nColumn names:")
print(df.columns.tolist())
print("\nFirst three hospitals:")
print(df.head(3).to_string(index=False))

## filter out state and info needed

df = df[df['State'] == 'MA']
df = df.rename(columns={
    'Facility Name': 'name',
    'Address': 'address',
    'City/Town': 'city',
    'State': 'state',
    'ZIP Code': 'zip',
    'Hospital Type': 'type',
    'Hospital overall rating': 'rating',
    'Emergency Services': 'emergency',
})
df = df[['name','address','city','state','zip','type','rating','emergency']]
df['rating'] = pd.to_numeric(df['rating'], errors='coerce')

## import coord info

import pgeocode
nomi = pgeocode.Nominatim('us')
df['zip'] = df['zip'].astype(str).str[:5].str.zfill(5)
geo = nomi.query_postal_code(df['zip'].tolist())
df['latitude'] = geo['latitude'].values
df['longitude'] = geo['longitude'].values
df = df.dropna(subset=['latitude','longitude'])

## save 

df.to_csv('data/clean/hospitals.csv', index=False)