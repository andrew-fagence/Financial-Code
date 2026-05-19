import os
import json
import requests
import gspread
import pandas as pd
import fredapi as fa
from google.oauth2.service_account import Credentials

# 1. Load API keys securely from environment variables
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY")
FRED_API_KEY = os.environ.get("FRED_API_KEY")
gcp_credentials_json = os.environ.get("GCP_CREDENTIALS")

# 2. Alpha Vantage - Currency Exchange
url = f'https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=USD&to_currency=JPY&apikey={ALPHA_VANTAGE_KEY}'
r = requests.get(url)
data = r.json()
print("Alpha Vantage Data:", data)

# 3. Google Sheets Setup
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
# Load credentials from the secure JSON string
creds_dict = json.loads(gcp_credentials_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

sheet_id = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
sheet = client.open_by_key(sheet_id)
wb = sheet.sheet1 # Fixing the undefined 'wb' variable from your original code

values_list = wb.row_values(1)
print("Sheet Row 1:", values_list)

# 4. FRED API Setup
fred = fa.Fred(FRED_API_KEY)

# Fetch Core CPI
CPICoreGet = fred.get_series('CPILFESL')
CPICore = CPICoreGet.tail()
print("Core CPI:\n", CPICore)

# Update Google Sheet with the last 3 values
for i, col_offset in enumerate(range(2, 8, 2)): # Maps to columns 2/3, 4/5, 6/7
    val = CPICore.iloc[2 + i]
    date_val = CPICore.index[2 + i]
    date_str = date_val.strftime('%Y-%m-%d')
    
    print(f"Updating Cell: Date={date_str}, Value={val}")
    wb.update_cell(2, col_offset, date_str)     # date
    wb.update_cell(2, col_offset + 1, val)      # value

# Fetch CPIAUCSL
cpi_headline = fred.get_series('CPIAUCSL')
print("Headline CPI:\n", cpi_headline.tail())

# Fetch PPIACO
ppi = fred.get_series('PPIACO')
print("PPI:\n", ppi.tail())

# 5. ONS Data
ons_url = "https://api.beta.ons.gov.uk/v1/datasets"
ons_data = requests.get(ons_url).json()

print("ONS Datasets:")
for e in ons_data.get("items", []):
    print(e["id"])
