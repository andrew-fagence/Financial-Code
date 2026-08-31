import pandas as pd
import requests
import io
import time
import json
import os
import gspread
from google import genai
from bs4 import BeautifulSoup

# Standard browser headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9'
}

def fetch_with_retry(url: str, retries: int = 3, timeout_sec: int = 15) -> str:
    """Fetches a URL with strict timeouts and retry logic to bypass 504 Server Timeouts."""
    for attempt in range(retries):
        try:
            res = requests.get(url, headers=HEADERS, timeout=timeout_sec)
            res.raise_for_status()
            return res.text
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise Exception(f"Failed after {retries} attempts. Last network error: {e}")
            sleep_time = 3 * (attempt + 1)
            print(f"Network hiccup ({e}). Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

def get_fed_rate() -> float:
    url = "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/1.json"
    json_text = fetch_with_retry(url)
    data = json.loads(json_text)
    return float(data['refRates'][0]['percentRate'])

def get_ecb_rate() -> float:
    url = "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?lastNObservations=1&format=csvdata"
    csv_text = fetch_with_retry(url)
    df = pd.read_csv(io.StringIO(csv_text))
    return float(df['OBS_VALUE'].iloc[0])

def get_boe_rate() -> float:
    url = "https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp"
    html_text = fetch_with_retry(url)
    tables = pd.read_html(io.StringIO(html_text))
    return float(tables[0].iloc[0, 1])

def get_boj_rate() -> float:
    url = "https://tradingeconomics.com/japan/interest-rate"
    html_text = fetch_with_retry(url)
    tables = pd.read_html(io.StringIO(html_text))
    for df in tables:
        if 'Actual' in df.columns and 'Highest' in df.columns:
            return float(df['Actual'].iloc[0])
    raise Exception("Could not find the BOJ interest rate table on Trading Economics.")

def get_trading_economics_context(url: str) -> str:
    html_text = fetch_with_retry(url)
    soup = BeautifulSoup(html_text, 'html.parser')
    description_container = soup.find(id="description")
    if description_container:
        return description_container.get_text(separator=' ', strip=True)
    return "No explicit macroeconomic guidance was found in the description container."

def get_ai_summary(client: genai.Client, bank_name: str, rate: float, outlook_context: str) -> str:
    prompt = (
        f"The current central bank interest rate for the {bank_name} is {rate}%. "
        f"Current Forward Outlook Signal: {outlook_context}. "
        "Based on this explicit guidance, write a strict 15-word maximum sentiment summary."
    )
    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"AI generation failed: {e}"

def update_google_sheets(spreadsheet_id: str, credentials_json_str: str, data: dict):
    try:
        print("Connecting to Google Sheets...")
        # Parses the JSON string from the GitHub Secret directly into a dictionary
        creds_dict = json.loads(credentials_json_str)
        gc = gspread.service_account_from_dict(creds_dict)
        
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.get_worksheet(0)

        update_payload = [
            {'range': 'H34', 'values': [[data['fed_rate']]]},
            {'range': 'H35', 'values': [[data['fed_summary']]]},
            {'range': 'H36', 'values': [[data['ecb_rate']]]},
            {'range': 'H37', 'values': [[data['ecb_summary']]]},
            {'range': 'H38', 'values': [[data['boe_rate']]]},
            {'range': 'H39', 'values': [[data['boe_summary']]]},
            {'range': 'K34', 'values': [[data['boj_rate']]]},
            {'range': 'K35', 'values': [[data['boj_summary']]]}
        ]

        worksheet.batch_update(update_payload)
        print("✅ Successfully exported all interest rates and sentiments to Google Sheets!")

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ Error: Spreadsheet ID '{spreadsheet_id}' not found. Verify the ID or check if you shared the sheet with your service account email.")
    except Exception as e:
        print(f"❌ Failed to update Google Sheets: {e}")

if __name__ == "__main__":
    # --- FETCH SECRETS FROM GITHUB ACTIONS ENVIRONMENT ---
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GCP_CREDENTIALS = os.environ.get("GCP_CREDENTIALS")
    SPREADSHEET_ID = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"

    if not GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY environment variable is not set.")
        exit(1)
    if not GCP_CREDENTIALS:
        print("❌ Error: GCP_CREDENTIALS environment variable is not set.")
        exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)

    print("Fetching the latest interest rates and webpage context... (This might take a few seconds)\n")

    try:
        fed = get_fed_rate()
        print(f"🇺🇸 FED Rate: {fed:.2f}% (EFFR)")

        ecb = get_ecb_rate()
        print(f"🇪🇺 ECB Rate: {ecb:.2f}%")

        boe = get_boe_rate()
        print(f"🇬🇧 BOE Rate: {boe:.2f}%")

        boj = get_boj_rate()
        print(f"🇯🇵 BOJ Rate: {boj:.2f}%")

        print("\nGenerating separate AI sentiment summaries from Trading Economics...\n")

        fed_url = "https://tradingeconomics.com/united-states/interest-rate"
        fed_context = get_trading_economics_context(fed_url)
        fed_summary = get_ai_summary(client, "Federal Reserve (FED)", fed, fed_context)
        print(f"🇺🇸 FED AI Summary:\n\"{fed_summary}\"\n")

        ecb_url = "https://tradingeconomics.com/euro-area/interest-rate"
        ecb_context = get_trading_economics_context(ecb_url)
        ecb_summary = get_ai_summary(client, "European Central Bank (ECB)", ecb, ecb_context)
        print(f"🇪🇺 ECB AI Summary:\n\"{ecb_summary}\"\n")

        boe_url = "https://tradingeconomics.com/united-kingdom/interest-rate"
        boe_context = get_trading_economics_context(boe_url)
        boe_summary = get_ai_summary(client, "Bank of England (BOE)", boe, boe_context)
        print(f"🇬🇧 BOE AI Summary:\n\"{boe_summary}\"\n")

        boj_url = "https://tradingeconomics.com/japan/interest-rate"
        boj_context = get_trading_economics_context(boj_url)
        boj_summary = get_ai_summary(client, "Bank of Japan (BOJ)", boj, boj_context)
        print(f"🇯🇵 BOJ AI Summary:\n\"{boj_summary}\"\n")

        data_payload = {
            'fed_rate': f"{fed:.2f}",
            'fed_summary': fed_summary,
            'ecb_rate': f"{ecb:.2f}",
            'ecb_summary': ecb_summary,
            'boe_rate': f"{boe:.2f}",
            'boe_summary': boe_summary,
            'boj_rate': f"{boj:.2f}",
            'boj_summary': boj_summary
        }

        update_google_sheets(SPREADSHEET_ID, GCP_CREDENTIALS, data_payload)

    except Exception as e:
        print(f"\n❌ A critical error occurred: {e}")
