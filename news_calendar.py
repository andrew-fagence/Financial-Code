import os
import json
import re
import dateutil.parser
import pytz

from sbvirtualdisplay import Display
from seleniumbase import Driver
from bs4 import BeautifulSoup

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
SERVICE_ACCOUNT_FILE = 'forexdailybias-5ce3a8ede6c9.json'  # Local fallback
SPREADSHEET_ID = '1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU'
SHEET_TAB_NAME = 'Calendar'

def get_impact_rating(col):
    """
    Detects the impact rating (Low, Medium, High) of an event from its cell HTML.
    Uses three fallback strategies: direct text, class attributes, and star icon counts.
    """
    text = col.get_text(strip=True).lower()
    if "★★★" in text or "high" in text:
        return "High"
    if "★★" in text or "med" in text or "medium" in text:
        return "Medium"
    if "★" in text or "low" in text:
        return "Low"

    classes = col.get("class", [])
    for child in col.find_all(True):
        classes.extend(child.get("class", []))
    class_str = " ".join(classes).lower()

    if any(k in class_str for k in ["high", "impact-high", "impact3", "impact-3", "critical", "important"]):
        return "High"
    if any(k in class_str for k in ["med", "moderate", "impact-medium", "impact-med", "impact2", "impact-2"]):
        return "Medium"
    if any(k in class_str for k in ["low", "minor", "impact-low", "impact1", "impact-1"]):
        return "Low"

    star_tags = col.find_all(lambda tag: "star" in tag.name or any("star" in c.lower() for c in tag.get("class", [])))
    star_count = len(star_tags)

    html_str = str(col)
    unicode_count = html_str.count("★")
    star_count = max(star_count, unicode_count)

    if star_count == 3 or star_count > 3:
        return "High"
    elif star_count == 2:
        return "Medium"
    elif star_count == 1:
        return "Low"

    return "N/A"

def convert_to_uk_time(date_obj, time_str):
    """
    Combines a date object with a time string (e.g., '4:15 AM'),
    interprets it in UTC, and converts it to Europe/London (UK) time.
    """
    if not time_str or time_str.strip() == "":
        return date_obj.strftime("%Y-%m-%d"), ""
    try:
        time_str = time_str.strip()
        combined_str = f"{date_obj.strftime('%Y-%m-%d')} {time_str}"
        parsed_dt = dateutil.parser.parse(combined_str)
        
        utc_tz = pytz.timezone('UTC')
        parsed_dt_utc = utc_tz.localize(parsed_dt)
        
        london_tz = pytz.timezone('Europe/London')
        dt_london = parsed_dt_utc.astimezone(london_tz)

        # 12-hour format with lowercase am/pm, removing leading zero from hour
        time_uk_formatted = dt_london.strftime('%I:%M %p').lower().lstrip('0')
        return dt_london.strftime('%Y-%m-%d'), time_uk_formatted
    except Exception:
        return date_obj.strftime("%Y-%m-%d"), time_str

def update_forex_calendar():
    # Start a virtual display so Chrome can run headlessly but bypass detection
    display = Display(visible=0, size=(1440, 1880))
    display.start()
    
    events = []
    
    try:
        print("Initializing SeleniumBase Driver in UC (Undetected-Chromedriver) Mode...")
        driver = Driver(uc=True)

        direct_calendar_url = "https://eia.autochartist.com/calendar/?broker_id=826&showall=true&nextdays=3&token=69e1c0ff09f3435c9d6978f7fef094ba&expire=1795989600&user=Alpha-Capital-Group&locale=en/calendar&timezone=UTC"

        print(f"Loading calendar widget directly: {direct_calendar_url}")
        driver.open(direct_calendar_url)

        print("Waiting for calendar events to render...")
        driver.sleep(10)

        html_content = driver.get_page_source()
        soup = BeautifulSoup(html_content, "html.parser")
        rows = soup.find_all("tr")
        print(f"Total table rows found: {len(rows)}")

        current_date_obj = None
        prefix_map = {"US:": "USD", "EMU:": "EUR", "GB:": "GBP", "JP:": "JPY"}

        for row in rows:
            cols = row.find_all(["td", "th"])
            if cols:
                first_cell_text = cols[0].get_text(strip=True)
                if first_cell_text == "Time":
                    # Only append header once (prevents duplicate headers if table repeats it daily)
                    if not events:
                        events.append(['Title', 'Country', 'Date', 'Time (UK)', 'Previous', 'Forecast'])
                    continue

                # Date group row (1 column spanning full width)
                if len(cols) == 1:
                    date_text = cols[0].get_text(strip=True)
                    try:
                        current_date_obj = dateutil.parser.parse(date_text)
                    except Exception as e:
                        print(f"Error parsing date header '{date_text}': {e}")
                    continue

                # Standard event row
                if len(cols) >= 3:
                    if get_impact_rating(cols[2]) != "High":
                        continue

                    raw_time = cols[0].get_text(strip=True)
                    raw_event = cols[1].get_text(strip=True)
                    raw_prior = cols[3].get_text(strip=True) if len(cols) > 3 else ""
                    raw_consensus = cols[4].get_text(strip=True) if len(cols) > 4 else ""

                    prior_val = raw_prior if raw_prior else "N/A"
                    consensus_val = raw_consensus if raw_consensus else "N/A"

                    matched_prefix = None
                    for prefix in prefix_map:
                        if raw_event.startswith(prefix):
                            matched_prefix = prefix
                            break

                    if matched_prefix:
                        currency = prefix_map[matched_prefix]
                        clean_event_name = raw_event[len(matched_prefix):].strip()

                        words_to_remove = ["United Kingdom", "Euro Area", "Japan", "United States", "US"]
                        for word in words_to_remove:
                            clean_event_name = re.sub(r'\b' + re.escape(word) + r'\b', '', clean_event_name)

                        clean_event_name = " ".join(clean_event_name.split())

                        if current_date_obj:
                            uk_date, uk_time = convert_to_uk_time(current_date_obj, raw_time)
                        else:
                            uk_date, uk_time = "", raw_time

                        row_data = [clean_event_name, currency, uk_date, uk_time, prior_val, consensus_val]
                        events.append(row_data)

    finally:
        try:
            driver.quit()
        except Exception as e:
            print(f"Error closing driver: {e}")
        display.stop()

    if events and len(events) > 1: # Checking > 1 to ensure we have more than just the header
        print("\n--- Scraped Economic Events ---")
        for idx, event in enumerate(events[1:], start=1):
            print(f"Event {idx}: {event}")

        print("\nUploading results to Google Spreadsheet...")
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive"
            ]

            # Reintroduced your original secure environmental variable logic
            gcp_credentials_json = os.environ.get("GCP_CREDENTIALS")
            if gcp_credentials_json:
                print("Loading credentials from GCP_CREDENTIALS environment variable...")
                creds_dict = json.loads(gcp_credentials_json)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            else:
                print(f"Loading credentials from fallback file: {SERVICE_ACCOUNT_FILE}")
                # Resolve potential missing extension logic from the colab block
                creds_file = SERVICE_ACCOUNT_FILE
                if not os.path.exists(creds_file) and os.path.exists(creds_file + ".json"):
                    creds_file = creds_file + ".json"
                creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)

            client = gspread.authorize(creds)
            sheet = client.open_by_key(SPREADSHEET_ID)

            try:
                worksheet = sheet.worksheet(SHEET_TAB_NAME)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = sheet.add_worksheet(title=SHEET_TAB_NAME, rows=100, cols=6)

            # Clear old content and update using append_rows (compatible with newest gspread)
            worksheet.clear()
            worksheet.append_rows(events)

            print("Success! Dashboard spreadsheet has been updated.")

        except Exception as sheet_err:
            print(f"Error uploading to Google Spreadsheet: {sheet_err}")
    else:
        print("\nNo high impact events could be parsed for this timeframe.")

if __name__ == "__main__":
    update_forex_calendar()
