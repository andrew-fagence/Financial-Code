import os
import json
import gspread
import requests
import fear_and_greed
from google.oauth2.service_account import Credentials

def update_market_data():
    try:
        # 1. Fetch Stock Market Fear & Greed Index
        print("Fetching Stock Market Fear & Greed Index...")
        stock_data = fear_and_greed.get()
        stock_score = round(stock_data.value)
        stock_sentiment = stock_data.description.title()
        print(f"Stock Market: {stock_score} ({stock_sentiment})")

        # 2. Fetch Crypto Fear & Greed Index
        print("Fetching Crypto Fear & Greed Index...")
        crypto_url = "https://api.alternative.me/fng/?limit=1"
        crypto_response = requests.get(crypto_url)
        crypto_response.raise_for_status()
        crypto_data = crypto_response.json()['data'][0]

        crypto_score = int(crypto_data['value'])
        crypto_sentiment = crypto_data['value_classification'].title()
        print(f"Crypto Market: {crypto_score} ({crypto_sentiment})")

        # 3. Authenticate and connect to Google Sheets securely
        print("Connecting to Google Sheets...")
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        
        # Load Google Credentials from GitHub Secrets
        gcp_credentials_json = os.environ.get("GCP_CREDENTIALS")
        if not gcp_credentials_json:
            raise ValueError("GCP_CREDENTIALS environment variable is missing!")
            
        creds_dict = json.loads(gcp_credentials_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)

        # 4. Open the sheet
        SPREADSHEET_ID = '1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU'
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Sheet1")

        # 5. Push data to spreadsheet rows
        print("Pushing data to spreadsheet...")

        # Stock Market updates (Cells E40 & E41)
        sheet.update_acell('E40', stock_score)
        sheet.update_acell('E41', stock_sentiment)

        # Crypto updates (Cells E43 & E44)
        sheet.update_acell('E43', crypto_score)
        sheet.update_acell('E44', crypto_sentiment)

        print("All data successfully synced to Google Sheets!")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    update_market_data()
