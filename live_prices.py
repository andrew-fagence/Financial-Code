import json
import os
import gspread
from google.oauth2.service_account import Credentials

if not os.path.exists('prices.json'):
    raise FileNotFoundError("prices.json not found! JS script failed.")

with open('prices.json', 'r') as f:
    live_data = json.load(f)

cell_mapping = {
    'TVC:DXY': 'B41',
    'FX:JPYBASKET': 'B42',
    'OANDA:EURGBP': 'B44',
    'OANDA:EURUSD': 'B45',
    'OANDA:GBPUSD': 'B46',
    'OANDA:GBPJPY': 'B47',
    'OANDA:EURJPY': 'B48',
    'Vantage:SP500': 'B34', # Fixed from Vantage:SP500
    'CAPITALCOM:US100': 'B35',
    'TVC:USOIL': 'E34',
    'OANDA:XAUUSD': 'E35',
    'OANDA:XAGUSD': 'E36',
    'CRYPTO:BTCUSD': 'E38',
    'TVC:US02Y': 'B37',
    'TVC:US10Y': 'B38',
    'CBOE:VIX': 'H41',
    'Vantage:GER40': 'H42'
}

percentage_symbols = ['TVC:US02Y', 'TVC:US10Y']

updates = []
for item in live_data:
    symbol = item.get('symbol')
    price = item.get('price')

    if symbol in cell_mapping:
        try:
            formatted_value = float(price)
            if symbol in percentage_symbols:
                formatted_value = formatted_value / 100
        except (ValueError, TypeError):
            formatted_value = price

        updates.append({
            'range': cell_mapping[symbol],
            'values': [[formatted_value]]
        })

print("Authenticating Google account...")
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# Load Service Account credentials from GitHub Secrets (passed as Environment Variable)
gcp_creds_json = os.environ.get('GCP_CREDENTIALS')
if not gcp_creds_json:
    raise ValueError("GCP_CREDENTIALS environment variable not found!")

creds_dict = json.loads(gcp_creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)

SPREADSHEET_ID = '1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU'
print(f"Connecting to Spreadsheet")
sh = gc.open_by_key(SPREADSHEET_ID)
worksheet = sh.sheet1

print(f"Sending {len(updates)} dynamic updates to Google Sheets...")
worksheet.batch_update(updates)
print("✅ Google Spreadsheet successfully updated with live data!")
