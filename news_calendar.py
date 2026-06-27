import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime
import pytz

# --- CONFIGURATION ---
SERVICE_ACCOUNT_FILE = 'forexdailybias-5ce3a8ede6c9.json'  # Local fallback
SPREADSHEET_ID = '1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU'
SHEET_TAB_NAME = 'Calendar'

def update_forex_calendar():
    print("Fetching High Impact news from ForexFactory JSON Feeds...")

    # Endpoints for Last Week, This Week, and Next Week
    urls = [
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    events = []

    # Loop through the URLs and aggregate the data
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            events.extend(response.json())
            print(f"Successfully fetched: {url.split('/')[-1]}")
        except Exception as e:
            print(f"Failed to fetch data from {url}: {e}")

    if not events:
        print("No calendar data could be fetched.")
        return

    # Set up UK Timezone
    uk_tz = pytz.timezone("Europe/London")
    high_impact_news = []

    for event in events:
        impact = str(event.get("impact", "")).strip().lower()
        if impact == "high":
            title = event.get("title", "").strip()
            country = event.get("country", "").strip()
            date_str = event.get("date", "").strip() # Typical Format: "2026-06-10T08:30:00-04:00"

            try:
                # Parse the ISO date string (including its original timezone offset)
                dt_obj = datetime.fromisoformat(date_str)

                # Failsafe: If the API ever drops the offset, assume UTC to prevent crashes
                if dt_obj.tzinfo is None:
                    dt_obj = pytz.utc.localize(dt_obj)

                # Convert the time to UK time (Automatically handles GMT/BST)
                uk_dt_obj = dt_obj.astimezone(uk_tz)

                # Format to match Javascript ISODate match logic (YYYY-MM-DD)
                formatted_date = uk_dt_obj.strftime("%Y-%m-%d")
                # Format time string cleanly (e.g., "8:30 am")
                formatted_time = uk_dt_obj.strftime("%I:%M %p").lstrip("0").lower()

            except ValueError:
                # Fallback if the date format slightly varies and parsing breaks entirely
                formatted_date = date_str[:10]
                formatted_time = date_str[11:16] + " (Unconverted)"

            high_impact_news.append([title, country, formatted_date, formatted_time])

    print(f"\nFound {len(high_impact_news)} High Impact events across the week. Writing to Google Sheets...")

    if not high_impact_news:
        print("No high impact events found for the requested timeframe.")
        return

    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]

        # Prioritize loading credentials from environment variable JSON
        gcp_credentials_json = os.environ.get("GCP_CREDENTIALS")
        if gcp_credentials_json:
            print("Loading credentials from GCP_CREDENTIALS environment variable...")
            creds_dict = json.loads(gcp_credentials_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            print(f"Loading credentials from fallback file: {SERVICE_ACCOUNT_FILE}")
            creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)

        client = gspread.authorize(creds)

        # Open Target Spreadsheet
        sheet = client.open_by_key(SPREADSHEET_ID)

        # Get or Create the dedicated "Calendar" Sheet tab
        try:
            worksheet = sheet.worksheet(SHEET_TAB_NAME)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=SHEET_TAB_NAME, rows=100, cols=4)

        # Build Data Payload
        upload_data = [["Title", "Country", "Date", "Time (UK)"]]
        upload_data.extend(high_impact_news)

        # Overwrite previous data with fresh calendar values
        worksheet.clear()
        worksheet.append_rows(upload_data)

        print("Success! Dashboard spreadsheet has been updated.")

    except Exception as e:
        print(f"Google Sheets update failed. Error: {e}")

if __name__ == "__main__":
    update_forex_calendar()
