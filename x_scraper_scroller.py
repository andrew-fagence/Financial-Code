import datetime
import json
import glob
import os
import re
import subprocess
import shutil
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from email.utils import parsedate_to_datetime

# Config
SPREADSHEET_ID = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
CREDENTIALS_FILE = "forexdailybias-5ce3a8ede6c9.json"  # Fallback path
DATA_DIR = "./x-scraper/data" # Base directory where the scraper outputs files

def ensure_config_file(max_tweets=15):
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
    Finds playwright_cookies.json in the repository directory,
    cleans legacy or invalid sameSite values (like 'no_restriction', 'unspecified', or null),
    converts cookie attributes to comply strictly with Playwright's expectations,
    and saves the cleaned cookies to bypass the login phase.
    """
    root_path = "./playwright_cookies.json"
    repo_cookies_path = "./x-scraper/playwright_cookies.json"

    # 1. Check if the user uploaded the file to the root folder
    if os.path.exists(root_path):
        print(f"Found cookie file at root: {root_path}. Moving to scraper folder...")
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

                # Handle expires conversion
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
            cwd="./x-scraper",  # Fixed path to operate relative to GitHub repo root
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

def update_google_sheet_with_tweets(accounts):
    all_extracted_tweets = []  # Will store tuples of (datetime_object, sanitized_content)

    for acc in accounts:
        username = acc["username"]

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
            if count >= 5:  # Restricts output to exactly 5 tweets per account
                break
            content = tweet.get("text", "").strip()
            if not content:
                continue  # Skip empty messages

            # --- DATA SANITIZATION ---
            # Remove boilerplate prefixes
            content = re.sub(r"^BREAKING:\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"^UPDATE:\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"^EXCLUSIVE:\s*", "", content, flags=re.IGNORECASE)
            
            # Remove specific custom phrases
            content = re.sub(r"🔴\s*More on", "", content, flags=re.IGNORECASE)
            content = re.sub(r"🔴\s*LIVE updates:", "", content, flags=re.IGNORECASE)
            content = re.sub(r"Here's what we know\.", "", content, flags=re.IGNORECASE)
            
            # Remove the "For more on this and other news visit [URL]" section
            content = re.sub(r"\s*For more on this and other news visit.*$", "", content, flags=re.IGNORECASE)
            
            # Remove volume emojis specifically
            content = re.sub(r"🔊", "", content)
            
            # Match the whole sentence containing BOTH "reuters" and "podcast" and remove it completely
            content = re.sub(r"[^.!?\n]*(?:reuters[^.!?\n]*podcast|podcast[^.!?\n]*reuters)[^.!?\n]*[.!?\n]*", "", content, flags=re.IGNORECASE)
            
            # Remove all URLs (this naturally catches the URLs at the end of the tweet)
            content = re.sub(r"https?://\S+|www\.\S+", "", content)

            # Remove all hashtags
            content = re.sub(r"#\w+", "", content)

            # Sanitize ALL emojis out of text (including zero-width joiners, skin tones, and keycaps)
            content = re.sub(
                r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\u200d\ufe0f\U0001F1E6-\U0001F1FF\u20e3]",
                "",
                content
            )

            # Clean up double spaces created by the removals and trim all leading/trailing whitespace
            content = re.sub(r"\s+", " ", content).strip()

            if not content:
                continue  # Skip if cleaning left the message completely empty
            
            # Append a full stop only if the content does not end in a full stop (.), exclamation mark (!), or question mark (?)
            if not content.endswith(('.', '!', '?')):
                content += '.'

            # --- EXTRACT DATE FOR SORTING ---
            date_str = tweet.get("created_at") or tweet.get("date") or ""
            parsed_date = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
            
            if date_str:
                try:
                    # Attempt standard Twitter API date parsing
                    dt = parsedate_to_datetime(date_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    parsed_date = dt
                except Exception:
                    try:
                        # Attempt standard ISO 8601 parsing fallback
                        dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=datetime.timezone.utc)
                        parsed_date = dt
                    except Exception:
                        pass

            # Append as a tuple so we can sort them all globally later
            all_extracted_tweets.append((parsed_date, content))
            count += 1

    if not all_extracted_tweets:
        print("No tweet data was gathered. Review the Scraper Logs above to see why X blocked the extraction.")
        return

    # Sort the global pool of extracted tweets by Date, newest first (Descending)
    all_extracted_tweets.sort(key=lambda x: x[0], reverse=True)

    # Extract just the sanitized text back into a list format for Google Sheets
    all_rows_to_write = [[t[1]] for t in all_extracted_tweets]

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

        # Connect to or create the "News" worksheet
        worksheet = None
        try:
            worksheet = sh.worksheet("News")
        except gspread.exceptions.WorksheetNotFound:
            print("Creating worksheet 'News'...")
            worksheet = sh.add_worksheet(title="News", rows="100", cols="5")

        print(f"Clearing old content in worksheet '{worksheet.title}'...")
        worksheet.clear()

        print(f"Writing {len(all_rows_to_write)} records to worksheet '{worksheet.title}'...")
        worksheet.update(range_name='A1', values=all_rows_to_write)

        # --- Polish spreadsheet layout and formatting ---
        print("Applying clean table formatting and auto-resizing columns...")
        try:
            # Enable word wrapping on Column A (the formatted tweet column)
            worksheet.format('A:A', {'wrapStrategy': 'WRAP'})
        except Exception as format_err:
            print(f"Word wrapping failed: {format_err}")

        try:
            # Automatically resize Column A so no text is cut off
            worksheet.columns_auto_resize(0, 1)
        except Exception as resize_err:
            print(f"Auto-resizing failed: {resize_err}")

        print("News sheet updated successfully.")

    except Exception as e:
        print(f"Failed to write to Google Sheet: {e}")

if __name__ == "__main__":
    # Define the accounts to scrape (exactly 5 tweets each will be displayed, without author prefixes)
    accounts = [
        {"username": "Reuters", "display_name": "Reuters"},
        {"username": "AP", "display_name": "The Associated Press"},
        {"username": "AJENews", "display_name": "Al Jazeera Breaking News"}
    ]

    # Generate config.ini for the scraper using environment variables
    ensure_config_file(max_tweets=15)
    
    # 1. Ensure codebase is patched to support multiple modal designs and "Continue" buttons
    patch_scraper_source()

    # 2. Automatically clean, structure, and sanitize user cookies before scraping runs
    clean_and_move_cookies()

    # 3. Execute the scraping process for all targeted accounts
    success = scrape_all_accounts(accounts)
    
    if success:
        update_google_sheet_with_tweets(accounts)
