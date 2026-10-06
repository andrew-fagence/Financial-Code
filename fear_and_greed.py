import os
import sys
import json
import time
import gspread
import requests
from google.oauth2.service_account import Credentials

def update_market_data():
    try:
        # 1. Fetch Stock Market Fear & Greed Index (Direct CNN API Call)
        print("Fetching Stock Market Fear & Greed Index...")
        cnn_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        cnn_response = requests.get(cnn_url, headers=headers)
        cnn_response.raise_for_status()
        
        cnn_data = cnn_response.json().get('fear_and_greed', {})
        stock_score = round(cnn_data.get('score', 50))
        stock_sentiment = cnn_data.get('rating', 'neutral').title()
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
            raise ValueError("GCP_CREDENTIALS environment variable is missing from execution environment!")
            
        creds_dict = json.loads(gcp_credentials_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)

        # 4. Open the sheet
        SPREADSHEET_ID = '1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU'
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Sheet1")

        # 5. Push data to spreadsheet rows
        print("Pushing data to spreadsheet...")

        max_attempts = 10
        for attempt in range(1, max_attempts + 1):
            try:
                # Single Batch Update for Stock Market & Crypto (1 API Call)
                updates = [
                    {'range': 'E40', 'values': [[stock_score]]},
                    {'range': 'E41', 'values': [[stock_sentiment]]},
                    {'range': 'E43', 'values': [[crypto_score]]},
                    {'range': 'E44', 'values': [[crypto_sentiment]]}
                ]
                
                sheet.batch_update(updates)

                print("All data successfully synced to Google Sheets!")
                break  # Success, exit the retry loop
                
            except Exception as e:
                # Check if it's a 429 Quota Exceeded Error and if we have attempts left
                if '429' in str(e) and attempt < max_attempts:
                    print(f"Quota exceeded (429). Retrying attempt {attempt}/{max_attempts} in 10 seconds...")
                    time.sleep(10) # Pause before trying again so the API limit resets
                else:
                    # If it's a different error or we've maxed out on retries, raise the exception
                    raise e

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        # Terminate with a non-zero exit code so GitHub Actions registers the failure
        sys.exit(1)

if __name__ == "__main__":
    update_market_data()
