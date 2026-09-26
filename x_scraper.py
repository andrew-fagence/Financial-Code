import os
import json
import datetime
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Config
# Uses the environment variable from GitHub Secrets, falling back to your provided string for local testing
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")          
CHANNEL_ID = "1550229016441655497"
SPREADSHEET_ID = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
CREDENTIALS_FILE = "forexdailybias-5ce3a8ede6c9.json"  # Fallback for local testing

def update_discord_news_sheet():
    # 1. Grab channel messages from Discord API
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=100"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}

    print("Fetching messages from Discord...")
    response = requests.get(url, headers=headers)

    # Error Handling for Discord
    if response.status_code != 200:
        try:
            error_data = response.json()
            if error_data.get("code") == 50001:
                print("Error 50001: Missing Access. The bot lacks 'View Channel' or 'Read Message History' permissions for this channel.")
            else:
                print(f"Error fetching from Discord: {error_data}")
        except Exception:
            print(f"Error fetching from Discord: {response.text}")
        return

    # 2. Parse payload into a table structure
    rows_to_write = [["Date/Time", "Message", "Author"]]

    for msg in response.json():
        content = msg.get("content", "").strip()
        if not content:
            continue  # Skip empty messages

        author = msg.get("author", {}).get("username", "Unknown")
        timestamp_str = msg.get("timestamp", "")

        # Format the timestamp nicely
        try:
            dt = datetime.datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            formatted_time = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            formatted_time = timestamp_str

        rows_to_write.append([formatted_time, content, author])

    if len(rows_to_write) == 1:
        print("No messages found to write.")
        return

    # 3. Connect and update Google Sheet using oauth2client
    try:
        print("Authenticating with Google Sheets...")
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # Securely load credentials from GitHub Secrets (like your old scraper did)
        gcp_credentials_json = os.environ.get("GCP_CREDENTIALS")
        if gcp_credentials_json:
            creds_dict = json.loads(gcp_credentials_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)

        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SPREADSHEET_ID)

        # Check if tab exists, create if not
        try:
            worksheet = sh.worksheet("DiscordNews")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="DiscordNews", rows="150", cols="5")

        print("Clearing old data and writing new records...")
        worksheet.clear()
        
        # Write values in bulk
        worksheet.update(range_name='A1', values=rows_to_write)

        print("DiscordNews sheet updated successfully.")

    except Exception as e:
        print(f"Failed to write to Google Sheet: {e}")

if __name__ == "__main__":
    update_discord_news_sheet()
