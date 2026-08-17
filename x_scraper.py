import datetime
import json
import glob
import os
import subprocess
import shutil
import gspread
import zoneinfo
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
    Finds playwright_cookies.json in the current directory,
    cleans legacy or invalid sameSite values (like 'no_restriction', 'unspecified', or null),
    converts cookie attributes to comply strictly with Playwright's expectations,
    and saves the cleaned cookies to bypass the login phase.
    """
    root_path = "./playwright_cookies.json"
    repo_cookies_path = "./x-scraper/playwright_cookies.json"

    # 1. Check if the user uploaded the file to the root folder
    if os.path.exists(root_path):
        print(f"Found cookie file at root: {root_path}. Copying to scraper folder...")
        try:
            shutil.copy2(root_path, repo_cookies_path)
        except Exception as e:
            print(f"Failed to copy cookie file: {e}")

    # 2. Process and sanitize the cookie file if it exists in the target path
    if os.path.exists(repo_cookies_path):
        print(f"Sanitizing cookies inside {repo_cookies_path} to prevent sameSite validation errors...")
        try:
            with open(repo_cookies_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            # Wrap in a list if it's a single dictionary
            if isinstance(cookies, dict):
                cookies = [cookies]

            cleaned_cookies = []
            valid_samesite_values = {"Strict", "Lax", "None"}

            for cookie in cookies:
                cleaned_cookie = {}

                # Copy required fields
                if 'name' in cookie:
                    cleaned_cookie['name'] = str(cookie['name'])
                if 'value' in cookie:
                    cleaned_cookie['value'] = str(cookie['value'])
                else:
                    continue  # Skip invalid cookies without values

                # Copy standard optional fields
                if 'domain' in cookie:
                    cleaned_cookie['domain'] = str(cookie['domain'])
                if 'path' in cookie:
                    cleaned_cookie['path'] = str(cookie['path'])
                if 'secure' in cookie:
                    cleaned_cookie['secure'] = bool(cookie['secure'])
                if 'httpOnly' in cookie:
                    cleaned_cookie['httpOnly'] = bool(cookie['httpOnly'])

                # Handle expires conversion (Playwright expects unix timestamp 'expires', EditThisCookie uses 'expirationDate')
                if 'expires' in cookie:
                    cleaned_cookie['expires'] = cookie['expires']
                elif 'expirationDate' in cookie:
                    cleaned_cookie['expires'] = cookie['expirationDate']

                # Fix sameSite validation strictly
                if 'sameSite' in cookie:
                    s_val = cookie['sameSite']
                    if s_val is not None:
                        s_str = str(s_val).strip()
                        s_capitalized = s_str.capitalize()  # "lax" -> "Lax", "none" -> "None"

                        if s_capitalized in valid_samesite_values:
                            cleaned_cookie['sameSite'] = s_capitalized
                        elif s_str.lower() in ["no_restriction", "unspecified"]:
                            cleaned_cookie['sameSite'] = "None"
                        else:
                            # Let Playwright default by omitting the sameSite property completely
                            pass

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
    """
    Patches playwright_scraper.py with the ULTIMATE Network Interceptor.
    Bypasses all endpoint name checks and scans ALL network traffic for tweets.
    """
    file_path = "./x-scraper/src/playwright_scraper.py"
    if not os.path.exists(file_path):
        print(f"Scraper file not found at {file_path}. Skipping patch.")
        return False

    print(f"Injecting ULTIMATE Interceptor and Diagnostics into {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()

        # --- 1. UI SELECTOR PATCHES ---
        code = code.replace('input[autocomplete="username"]', 'input[autocomplete="username"], input[name="text"], input[placeholder*="username" i], input[placeholder*="Email" i]')
        code = code.replace('"text=Next"', '"text=/Next|Continue/i"')
        code = code.replace("'text=Next'", "'text=/Next|Continue/i'")
        code = code.replace('span:has-text("Next")', 'span:has-text("Next"), span:has-text("Continue")')
        code = code.replace("span:has-text('Next')", "span:has-text('Next'), span:has-text('Continue')")
        code = code.replace('span:has-text("Log in")', 'span:has-text("Log in"), span:has-text("Continue"), span:has-text("Sign in")')
        code = code.replace("span:has-text('Log in')", "span:has-text('Log in'), span:has-text('Continue'), span:has-text('Sign in')")

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)

        # --- 2. THE OMNI-INTERCEPTOR MONKEY PATCH ---
        monkey_patch = """
# --- THE ULTIMATE INTERCEPTOR PATCH ---
import time
import json
from typing import Dict, Any, Optional

def _recursive_find(obj, key):
    if isinstance(obj, dict):
        if key in obj: return obj
        for k, v in obj.items():
            res = _recursive_find(v, key)
            if res: return res
    elif isinstance(obj, list):
        for item in obj:
            res = _recursive_find(item, key)
            if res: return res
    return None

async def ultimate_intercept_response(self, response):
    # 1. Run the original interceptor so we don't break existing dependencies
    if hasattr(self, '_original_intercept_response'):
        await self._original_intercept_response(response)
        
    try:
        url = response.url
        # Catch ALL Twitter API traffic, regardless of endpoint name
        if 'graphql' in url.lower() or 'api.twitter.com' in url or 'api.x.com' in url:
            if response.request.resource_type in ["xhr", "fetch"]:
                try:
                    data = await response.json()
                    
                    # --- DIAGNOSTICS: Catch hidden Twitter bans/rate limits ---
                    if isinstance(data, dict):
                        if 'errors' in data:
                            self.logger.error(f"🚨 TWITTER API ERROR from {url.split('/')[-1].split('?')[0]}: {data['errors']}")
                        elif data.get('data', {}).get('user', {}).get('result', {}).get('__typename') == 'UserUnavailable':
                            self.logger.error(f"🚨 TWITTER ACCOUNT BANNED OR UNAVAILABLE: {data}")
                    
                    # --- AGGRESSIVE TWEET EXTRACTION ---
                    tweets_found = 0
                    def extract_tweets_recursively(obj):
                        nonlocal tweets_found
                        if isinstance(obj, dict):
                            # A valid tweet object always contains a 'legacy' dict with 'full_text'
                            if 'legacy' in obj and isinstance(obj['legacy'], dict) and 'full_text' in obj['legacy']:
                                legacy = obj['legacy']
                                tweet_id = legacy.get('id_str') or obj.get('rest_id')
                                
                                if not hasattr(self, 'scraped_tweet_ids'): self.scraped_tweet_ids = set()
                                if not hasattr(self, 'all_tweets'): self.all_tweets = []
                                
                                if tweet_id and tweet_id not in self.scraped_tweet_ids:
                                    user_info = _recursive_find(obj, 'screen_name') or {}
                                    
                                    tweet_data = {
                                        'id': tweet_id,
                                        'text': legacy.get('full_text', ''),
                                        'full_text': legacy.get('full_text', ''),
                                        'created_at': legacy.get('created_at', ''),
                                        'user': {
                                            'id': user_info.get('id_str', ''),
                                            'username': user_info.get('screen_name', 'financialjuice'),
                                            'display_name': user_info.get('name', 'FinancialJuice'),
                                        },
                                        'metrics': {},
                                        'lang': legacy.get('lang', 'en'),
                                        'hashtags': [],
                                        'urls': [],
                                        'media': [],
                                        'scraped_at': time.time()
                                    }
                                    
                                    self.all_tweets.append(tweet_data)
                                    self.scraped_tweet_ids.add(tweet_id)
                                    tweets_found += 1
                                    
                            for k, v in obj.items():
                                extract_tweets_recursively(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                extract_tweets_recursively(item)

                    extract_tweets_recursively(data)
                    
                    if tweets_found > 0:
                        endpoint = url.split('/')[-1].split('?')[0]
                        self.logger.info(f"🔥 BINGO! Extracted {tweets_found} tweets directly from {endpoint}")
                        
                except Exception as e:
                    pass
    except Exception as e:
        pass

# Dynamically apply the Omni-Interceptor at runtime
for obj_name, obj in list(locals().items()):
    if isinstance(obj, type) and hasattr(obj, '_intercept_response'):
        if not hasattr(obj, '_original_intercept_response'):
            obj._original_intercept_response = obj._intercept_response
        obj._intercept_response = ultimate_intercept_response
"""
        with open(file_path, 'r', encoding='utf-8') as f:
            current_code = f.read()

        if "THE ULTIMATE INTERCEPTOR PATCH" not in current_code:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write("\n" + monkey_patch)
            print("Successfully injected the Ultimate Interceptor monkey-patch!")

        return True
    except Exception as e:
        print(f"Failed to patch source code: {e}")
        return False

def scrape_all_accounts(accounts):
    print("Ensuring virtual display dependencies are installed...")
    # Install xvfb cleanly if it isn't already present in the environment
    subprocess.run(["apt-get", "install", "-y", "xvfb"], capture_output=True)

    success_count = 0
    for acc in accounts:
        username = acc["username"]
        print(f"Starting X-Scraper for {username}...\n")
        print(f"--- SCRAPER LOGS FOR {username} START ---")

        # Prefixing the command with xvfb-run to provide a virtual cloud monitor
        cmd = [
            "xvfb-run",
            "--auto-servernum",
            "uv",
            "run",
            "main.py",
            "user",
            "--username", username
        ]

        # Force Python to not buffer the output
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
    """
    Robustly looks for the scraper output file directly for a specific username,
    then falls back to a recursive search inside the scraper data directory.
    """
    direct_paths = [
        f"./x-scraper/data/{username}/tweets_{username}.json",
        f"./x-scraper/data/{username.lower()}/tweets_{username.lower()}.json",
        f"./x-scraper/data/tweets_{username}.json",
        f"./x-scraper/data/tweets_{username.lower()}.json"
    ]
    for path in direct_paths:
        if os.path.exists(path):
            return path

    # Fallback to recursive search
    list_of_files = glob.glob(f'{DATA_DIR}/**/*.json', recursive=True)
    # Ignore cookie configurations or other files
    valid_files = [
        f for f in list_of_files
        if username.lower() in os.path.basename(f).lower() and "cookie" not in os.path.basename(f).lower()
    ]
    if valid_files:
        return max(valid_files, key=os.path.getctime)

    return None

def parse_twitter_date(date_str):
    """
    Converts Twitter timestamp to a timezone-naive UTC datetime object.
    Falls back to the minimum datetime if parsing fails.
    """
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

        # 1. Locate the correct JSON file for the account
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
                continue  # Skip empty messages

            timestamp_str = tweet.get("created_at", "")
            dt_obj = parse_twitter_date(timestamp_str)

            # Format the timestamp nicely (YYYY-MM-DD HH:MM)
            try:
                dt = datetime.datetime.strptime(timestamp_str, "%a %b %d %H:%M:%S %z %Y")
                # Convert the time explicitly to UK timezone (handles GMT/BST automatically)
                dt = dt.astimezone(zoneinfo.ZoneInfo("Europe/London"))
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
        print("No tweet data was gathered. Review the Scraper Logs above to see why X blocked the extraction.")
        return

    # Sort globally by datetime descending (latest first)
    all_tweets.sort(key=lambda x: x["datetime"], reverse=True)

    # 2. Build rows structure
    rows_to_write = [["Date/Time", "Message", "Author"]]
    for t in all_tweets:
        rows_to_write.append([t["formatted_time"], t["content"], t["author"]])

    # 3. Connect and update Google Sheet using oauth2client
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # Use GCP Github Secrets when available
        gcp_credentials_json = os.environ.get("GCP_CREDENTIALS")
        if gcp_credentials_json:
            creds_dict = json.loads(gcp_credentials_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)

        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SPREADSHEET_ID)

        # Check for sheet name variations: "XNews" or "X_News"
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
        # Use named arguments to ensure compatibility across gspread v5.x and v6.x
        worksheet.update(range_name='A1', values=rows_to_write)

        # --- Polish spreadsheet layout and formatting ---
        print("Applying clean table formatting and auto-resizing columns...")
        try:
            # Make the header bold
            worksheet.format('A1:C1', {'textFormat': {'bold': True}})
        except Exception as format_err:
            print(f"Bold formatting omitted: {format_err}")

        try:
            # Enable word wrapping on Column B (the tweet message column)
            worksheet.format('B:B', {'wrapStrategy': 'WRAP'})
        except Exception as format_err:
            print(f"Word wrapping omitted: {format_err}")

        try:
            # Automatically resize columns A, B, and C so no dates or text are cut off
            worksheet.columns_auto_resize(0, 3)
        except Exception as resize_err:
            print(f"Auto-resizing omitted: {resize_err}")

        print("XNews sheet updated successfully.")

    except Exception as e:
        print(f"Failed to write to Google Sheet: {e}")


if __name__ == "__main__":
    # Define the accounts to scrape
    accounts = [
        {"username": "financialjuice", "display_name": "FinancialJuice"}
    ]

    # Generate config.ini for the scraper using environment variables
    ensure_config_file(max_tweets=70)

    # 1. Ensure codebase is patched to support multiple modal designs and "Continue" buttons
    patch_scraper_source()

    # 2. Automatically clean, structure, and sanitize user cookies before scraping runs
    clean_and_move_cookies()

    # 3. Execute the scraping process
    success = scrape_all_accounts(accounts)
    
    if success:
        update_google_sheet_with_tweets(accounts)
