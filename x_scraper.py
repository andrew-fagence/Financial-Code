import datetime
import json
import glob
import os
import subprocess
import shutil
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Config
SPREADSHEET_ID = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
CREDENTIALS_FILE = "forexdailybias-5ce3a8ede6c9.json"  # Fallback path
DATA_DIR = "./x-scraper/data" # Base directory where the scraper outputs files

def ensure_config_file(max_tweets=70):
    """
    Dynamically generates the config.ini file inside the cloned scraper directory
    using environment variables for security.
    """
    os.makedirs('./x-scraper/data', exist_ok=True)
    username = os.environ.get("TWITTER_USERNAME", "KnowOneScrape")
    email = os.environ.get("TWITTER_EMAIL", "andrew.s.fagence@gmail.com")
    password = os.environ.get("TWITTER_PASSWORD", "Creative1!")
    proxy_url = os.environ.get("PROXY_URL", "")
    use_proxy = "true" if proxy_url else "false"

    config_content = f"""[TWITTER]
username = {username}
email = {email}
password = {password}

[PROXY]
use_proxy = {use_proxy}
proxy_url = {proxy_url}

[AI]
enable_analysis = false

[SCRAPING]
output_directory = ./x-scraper/data
max_tweets_per_session = {max_tweets}
scroll_delay_min = 2.0
scroll_delay_max = 5.0
"""
    with open('./x-scraper/config.ini', 'w') as f:
        f.write(config_content)
    print("config.ini updated with settings!")

def clean_and_move_cookies():
    """
    Finds playwright_cookies.json in current directory, cleans legacy or invalid 
    sameSite values, and saves the cleaned cookies to the target scraper path.
    """
    root_path = "./playwright_cookies.json"
    repo_cookies_path = "./x-scraper/playwright_cookies.json"

    # Move cookie file from repo workspace to target directory if found
    if os.path.exists(root_path):
        print(f"Found cookie file at root: {root_path}. Moving to scraper folder...")
        try:
            shutil.copy2(root_path, repo_cookies_path)
        except Exception as e:
            print(f"Failed to move cookie file: {e}")

    if os.path.exists(repo_cookies_path):
        print(f"Sanitizing cookies inside {repo_cookies_path} to prevent sameSite validation errors...")
        try:
            with open(repo_cookies_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            if isinstance(cookies, dict):
                cookies = [cookies]

            cleaned_cookies = []
            valid_samesite_values = {"Strict", "Lax", "None"}

            for cookie in cookies:
                cleaned_cookie = {}

                if 'name' in cookie:
                    cleaned_cookie['name'] = str(cookie['name'])
                if 'value' in cookie:
                    cleaned_cookie['value'] = str(cookie['value'])
                else:
                    continue  # Skip invalid cookies without values

                if 'domain' in cookie:
                    cleaned_cookie['domain'] = str(cookie['domain'])
                if 'path' in cookie:
                    cleaned_cookie['path'] = str(cookie['path'])
                if 'secure' in cookie:
                    cleaned_cookie['secure'] = bool(cookie['secure'])
                if 'httpOnly' in cookie:
                    cleaned_cookie['httpOnly'] = bool(cookie['httpOnly'])

                if 'expires' in cookie:
                    cleaned_cookie['expires'] = cookie['expires']
                elif 'expirationDate' in cookie:
                    cleaned_cookie['expires'] = cookie['expirationDate']

                if 'sameSite' in cookie:
                    s_val = cookie['sameSite']
                    if s_val is not None:
                        s_str = str(s_val).strip()
                        s_capitalized = s_str.capitalize()

                        if s_capitalized in valid_samesite_values:
                            cleaned_cookie['sameSite'] = s_capitalized
                        elif s_str.lower() in ["no_restriction", "unspecified"]:
                            cleaned_cookie['sameSite'] = "None"

                cleaned_cookies.append(cleaned_cookie)

            with open(repo_cookies_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_cookies, f, indent=4)

            print("Cookie file sameSite properties successfully cleaned and standardized!")
            return True
        except Exception as e:
            print(f"Failed to clean cookie file: {e}")
            return False
    else:
        print("No playwright_cookies.json file detected. The script will fall back to username/password login.")
        return False

def patch_scraper_source():
    file_path = "./x-scraper/src/playwright_scraper.py"
    if not os.path.exists(file_path):
        print(f"Scraper file not found at {file_path}. Skipping patch.")
        return False

    print(f"Patching {file_path} to make authentication selectors more robust...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()

        patched_code = code
        original_username = 'input[autocomplete="username"]'
        robust_username = 'input[autocomplete="username"], input[name="text"], input[placeholder*="username" i], input[placeholder*="Email" i]'

        patched_code = patched_code.replace(f'"{original_username}"', f'"{robust_username}"')
        patched_code = patched_code.replace(f"'{original_username}'", f"'{robust_username}'")

        patched_code = patched_code.replace('"text=Next"', '"text=/Next|Continue/i"')
        patched_code = patched_code.replace("'text=Next'", "'text=/Next|Continue/i'")
        patched_code = patched_code.replace('span:has-text("Next")', 'span:has-text("Next"), span:has-text("Continue")')
        patched_code = patched_code.replace("span:has-text('Next')", "span:has-text('Next'), span:has-text('Continue')")

        patched_code = patched_code.replace('span:has-text("Log in")', 'span:has-text("Log in"), span:has-text("Continue"), span:has-text("Sign in")')
        patched_code = patched_code.replace("span:has-text('Log in')", "span:has-text('Log in'), span:has-text('Continue'), span:has-text('Sign in')")

        if patched_code != code:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(patched_code)
            print("Successfully patched playwright_scraper.py!")
            return True
        else:
            print("playwright_scraper.py is already up to date.")
            return False
    except Exception as e:
        print(f"Failed to patch source code: {e}")
        return False

def scrape_all_accounts(accounts):
    success_count = 0
    for acc in accounts:
        username = acc["username"]
        print(f"Starting X-Scraper for {username}...\n")
        print(f"--- SCRAPER LOGS FOR {username} START ---")

        # Runs xvfb-run to support headless browser execution on Linux
        cmd = [
            "xvfb-run",
            "--auto-servernum",
            "uv",
            "run",
            "main.py",
            "user",
            "--username", username
        ]

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        result = subprocess.run(
            cmd,
            cwd="./x-scraper",
            capture_output=True,
            text=True,
            env=env
        )

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"ERRORS/WARNINGS FOR {username}:")
            print(result.stderr)

        print(f"--- SCRAPER LOGS FOR {username} END ---\n")

        if result.returncode != 0:
            print(f"Scraper crashed or exited with an error code for {username}.")
        else:
            success_count += 1

    return success_count > 0

def find_scraped_file(username):
    direct_paths = [
        f"./x-scraper/data/{username}/tweets_{username}.json",
        f"./x-scraper/data/{username.lower()}/tweets_{username.lower()}.json",
        f"./x-scraper/data/tweets_{username}.json",
        f"./x-scraper/data/tweets_{username.lower()}.json"
    ]
    for path in direct_paths:
        if os.path.exists(path):
            return path

    list_of_files = glob.glob(f'{DATA_DIR}/**/*.json', recursive=True)
    valid_files = [
        f for f in list_of_files
        if username.lower() in os.path.basename(f).lower() and "cookie" not in os.path.basename(f).lower()
    ]
    if valid_files:
        return max(valid_files, key=os.path.getctime)

    return None

def parse_twitter_date(date_str):
    try:
        dt = datetime.datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.datetime.min

def update_google_sheet_with_tweets(accounts):
    all_tweets = []

    for acc in accounts:
        username = acc["username"]
        display_name = acc["display_name"]

        latest_file = find_scraped_file(username)
        if not latest_file:
            print(f"No scraped data found for {username}. Skipping extraction.")
            continue

        print(f"Parsing data from: {latest_file}")

        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to read JSON for {username}: {e}")
            continue

        tweets = data.get("tweets", [])
        if not tweets:
            print(f"No tweets found in the exported JSON file for {username}.")
            continue

        count = 0
        for tweet in tweets:
            if count >= 70:
                break
            content = tweet.get("text", "").strip()
            if not content:
                continue

            timestamp_str = tweet.get("created_at", "")
            dt_obj = parse_twitter_date(timestamp_str)

            try:
                dt = datetime.datetime.strptime(timestamp_str, "%a %b %d %H:%M:%S %z %Y")
                formatted_time = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                formatted_time = timestamp_str

            all_tweets.append({
                "datetime": dt_obj,
                "formatted_time": formatted_time,
                "content": content,
                "author": display_name
            })
            count += 1

    if not all_tweets:
        print("No tweet data was gathered.")
        return

    all_tweets.sort(key=lambda x: x["datetime"], reverse=True)

    rows_to_write = [["Date/Time", "Message", "Author"]]
    for t in all_tweets:
        rows_to_write.append([t["formatted_time"], t["content"], t["author"]])

    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        gcp_credentials_json = os.environ.get("GCP_CREDENTIALS")
        if gcp_credentials_json:
            creds_dict = json.loads(gcp_credentials_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)

        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SPREADSHEET_ID)

        worksheet = None
        for name in ["XNews", "X_News"]:
            try:
                worksheet = sh.worksheet(name)
                break
            except gspread.exceptions.WorksheetNotFound:
                continue

        if not worksheet:
            print("Creating worksheet 'XNews'...")
            worksheet = sh.add_worksheet(title="XNews", rows="100", cols="5")

        print(f"Clearing old content in worksheet '{worksheet.title}'...")
        worksheet.clear()

        print(f"Writing {len(rows_to_write) - 1} records...")
        worksheet.update(range_name='A1', values=rows_to_write)

        print("Applying formatting rules...")
        try:
            worksheet.format('A1:C1', {'textFormat': {'bold': True}})
        except Exception as err:
            print(f"Formatting failed: {err}")

        try:
            worksheet.format('B:B', {'wrapStrategy': 'WRAP'})
        except Exception as err:
            print(f"Wrap strategy failed: {err}")

        try:
            worksheet.columns_auto_resize(0, 3)
        except Exception as err:
            print(f"Auto-resize failed: {err}")

        print("XNews sheet updated successfully.")

    except Exception as e:
        print(f"Failed to write to Google Sheet: {e}")

if __name__ == "__main__":
    accounts = [
        {"username": "financialjuice", "display_name": "FinancialJuice"}
    ]

    ensure_config_file(max_tweets=70)
    patch_scraper_source()
    clean_and_move_cookies()
    success = scrape_all_accounts(accounts)
    if success:
        update_google_sheet_with_tweets(accounts)
