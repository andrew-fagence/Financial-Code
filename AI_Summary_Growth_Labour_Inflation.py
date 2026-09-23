import time
import json
import os
import gspread
from google import genai
from google.genai import types

def get_ai_summary_with_search(client: genai.Client, region: str, prompt: str) -> str:
    """Queries Gemini with the provided prompt."""
    for attempt in range(10):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            error_msg = str(e)
            
            # 1. ADD THIS BLOCK: Handle 429 Quota Exceeded errors
            if "429" in error_msg:
                if attempt < 9:
                    wait_time = 10 * (attempt + 1) # Incremental backoff (10s, 20s, 30s...)
                    print(f"[{region}] Rate limit exceeded (429). Retrying in {wait_time} seconds (Attempt {attempt + 2}/10)...")
                    time.sleep(wait_time)
                    continue

            # 2. Existing 503 high demand unavailability error check
            if "503" in error_msg and "UNAVAILABLE" in error_msg and "high demand" in error_msg:
                if attempt < 9:
                    print(f"[{region}] Model in high demand (503). Retrying in 5 seconds (Attempt {attempt + 2}/10)...")
                    time.sleep(5)
                    continue
                    
            return f"AI generation failed: {e}"

def update_google_sheets(spreadsheet_id: str, credentials_json_str: str, data: dict):
    for attempt in range(10):
        try:
            if attempt == 0:
                print("Connecting to Google Sheets...")
            else:
                print(f"Re-connecting to Google Sheets (Attempt {attempt + 1}/10)...")

            # Parses the JSON string from the GitHub Secret directly into a dictionary
            creds_dict = json.loads(credentials_json_str)
            gc = gspread.service_account_from_dict(creds_dict)
            
            sh = gc.open_by_key(spreadsheet_id)
            # Targeting the specific "Sentiments" sheet instead of index 0
            worksheet = sh.worksheet("Sentiments")

            update_payload = [
                {'range': 'A1', 'values': [[data['usd_summary']]]},
                {'range': 'A2', 'values': [[data['eur_summary']]]},
                {'range': 'A3', 'values': [[data['gbp_summary']]]},
                {'range': 'A4', 'values': [[data['jpy_summary']]]}
            ]

            worksheet.batch_update(update_payload)
            print("✅ Successfully exported all sentiments to the 'Sentiments' Google Sheet!")
            return # Exit function on successful update

        except gspread.exceptions.SpreadsheetNotFound:
            print(f"❌ Error: Spreadsheet ID '{spreadsheet_id}' not found. Verify the ID or check if you shared the sheet with your service account email.")
            return # Don't retry, it won't resolve a 404
        except gspread.exceptions.WorksheetNotFound:
            print(f"❌ Error: Worksheet 'Sentiments' not found in Spreadsheet '{spreadsheet_id}'. Please create it.")
            return # Don't retry, it won't resolve a missing tab
        except Exception as e:
            error_msg = str(e)
            # Checks explicitly for the 429 Quota Exceeded error
            if "429" in error_msg and "Quota exceeded" in error_msg:
                if attempt < 9:
                    print(f"Google Sheets rate limit exceeded (429). Retrying in 10 seconds (Attempt {attempt + 2}/10)...")
                    time.sleep(10)
                    continue
            print(f"❌ Failed to update Google Sheets: {e}")
            return # Exit if max retries hit or different error occurs

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

    print("Generating AI sentiment summaries with Google Search Grounding...\n")

    usd_prompt = "Give me a 100 word paragraph of the current sentiment of the USA inflation, growth and labour metrics that will affect the EURUSD and GBPUSD forex pairs for the next day. Dont give bias or even mention EURGBP, EURJPY or GBPJPY in your response. Just summarise and give sentiment on the USA inflation, growth and labour data."
    eur_prompt = "Give me a 100 word paragraph of the current sentiment of the EU inflation, growth and labour metrics that will affect the EURUSD, EURGBP and EURJPY forex pairs for the next day. Dont give bias or even mention GBPUSD or GBPJPY in your response. Just summarise and give sentiment on the EU inflation, growth and labour data."
    gbp_prompt = "Give me a 100 word paragraph of the current sentiment of the UK inflation, growth and labour metrics that will affect the EURGBP, GBPUSD and GBPJPY forex pairs for the next day. Dont give bias or even mention EURUSD or EURJPY in your response. Just summarise and give sentiment on the UK inflation, growth and labour data."
    jpy_prompt = "Give me a 100 word paragraph of the current sentiment of the Japan inflation, growth and labour metrics that will affect the EURJPY and GBPJPY forex pairs for the next day. Dont give bias or even mention EURUSD, EURGBP or GBPUSD in your response. Just summarise and give sentiment on the Japan inflation, growth and labour data."

    try:
        usd_summary = get_ai_summary_with_search(client, "USD", usd_prompt)
        print(f"🇺🇸 USD AI Summary:\n\"{usd_summary}\"\n")

        eur_summary = get_ai_summary_with_search(client, "EUR", eur_prompt)
        print(f"🇪🇺 EUR AI Summary:\n\"{eur_summary}\"\n")

        gbp_summary = get_ai_summary_with_search(client, "GBP", gbp_prompt)
        print(f"🇬🇧 GBP AI Summary:\n\"{gbp_summary}\"\n")

        jpy_summary = get_ai_summary_with_search(client, "JPY", jpy_prompt)
        print(f"🇯🇵 JPY AI Summary:\n\"{jpy_summary}\"\n")

        data_payload = {
            'usd_summary': usd_summary,
            'eur_summary': eur_summary,
            'gbp_summary': gbp_summary,
            'jpy_summary': jpy_summary
        }

        update_google_sheets(SPREADSHEET_ID, GCP_CREDENTIALS, data_payload)

    except Exception as e:
        print(f"\n❌ A critical error occurred: {e}")
