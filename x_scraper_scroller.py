import datetime
import json
import glob
import os
import re
import subprocess
import shutil
import time
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
    username = os.environ.get("TWITTER_USERNAME")
    email = os.environ.get("TWITTER_EMAIL")
    password = os.environ.get("TWITTER_PASSWORD")
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
    keeps ONLY the auth_token to force Twitter to generate fresh CSRF tokens (ct0),
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
                # KEEP ONLY auth_token TO PREVENT STALE ct0 (CSRF) TOKEN MISMATCHES!
                if cookie.get('name') != 'auth_token':
                    continue

                cleaned_cookie = {}

                # Copy required fields
                if 'name' in cookie:
                    cleaned_cookie['name'] = str(cookie['name'])
                if 'value' in cookie:
                    cleaned_cookie['value'] = str(cookie['value'])
                else:
                    continue  # Skip invalid cookies without values

                # Copy standard optional fields & force domain transition
                if 'domain' in cookie:
                    domain = str(cookie['domain'])
                    if 'twitter.com' in domain:
                        domain = domain.replace('twitter.com', 'x.com')
                    cleaned_cookie['domain'] = domain
                    
                if 'path' in cookie:
                    cleaned_cookie['path'] = str(cookie['path'])
                if 'secure' in cookie:
                    cleaned_cookie['secure'] = bool(cookie['secure'])
                else:
                    cleaned_cookie['secure'] = True  # Default to secure
                    
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
                            pass
                
                if cleaned_cookie.get('sameSite') == 'None':
                    cleaned_cookie['secure'] = True

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
    if hasattr(self, '_original_intercept_response'):
        await self._original_intercept_response(response)
        
    try:
        url = response.url
        if 'graphql' in url.lower() or 'api.twitter.com' in url or 'api.x.com' in url:
            if response.request.resource_type in ["xhr", "fetch"]:
                try:
                    data = await response.json()
                    
                    if isinstance(data, dict):
                        if 'errors' in data:
                            self.logger.error(f"🚨 TWITTER API ERROR from {url.split('/')[-1].split('?')[0]}: {data['errors']}")
                        elif data.get('data', {}).get('user', {}).get('result', {}).get('__typename') == 'UserUnavailable':
                            self.logger.error(f"🚨 TWITTER ACCOUNT BANNED OR UNAVAILABLE: {data}")
                    
                    tweets_found = 0
                    def extract_tweets_recursively(obj):
                        nonlocal tweets_found
                        if isinstance(obj, dict):
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
    subprocess.run(["apt-get", "install", "-y", "xvfb"], capture_output=True)

    success_count = 0
    for acc in accounts:
        username = acc["username"]
        print(f"Starting X-Scraper for {username}...\n")
        print(f"--- SCRAPER LOGS FOR {username} START ---")

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

    list_of_files = glob.glob(f'{DATA_DIR}/**/*.json', recursive=True)
    valid_files = [
        f for f in list_of_files
        if username.lower() in os.path.basename(f).lower() and "cookie" not in os.path.basename(f).lower()
    ]
    if valid_files:
        return max(valid_files, key=os.path.getctime)

    return None

def update_google_sheet_with_tweets(accounts):
    all_extracted_tweets = []  

    for acc in accounts:
        username = acc["username"]

        latest_file = find_scraped_file(username)
        data = {}
        if latest_file:
            print(f"Parsing data from: {latest_file}")
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Failed to read JSON for {username}: {e}")

        tweets = data.get("tweets", [])
        
        # --- ROBUST SYNDICATION FALLBACK LOGIC WITH PROXY ROTATION ---
        if not tweets:
            print(f"No tweets found in the exported JSON file for {username}. Attempting Syndication API fallback via proxy rotators...")
            try:
                import urllib.request
                import urllib.parse
                
                base_url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
                
                # A list of free public proxies to instantly bypass GitHub Actions IP bans (429)
                proxy_services = [
                    "",  # 1. Direct Connection (try first)
                    "https://api.codetabs.com/v1/proxy?quest=",  # 2. CodeTabs Open Proxy
                    "https://api.allorigins.win/raw?url="  # 3. AllOrigins CORS Proxy
                ]
                
                html = None
                for proxy in proxy_services:
                    try:
                        # Some proxies require the target URL to be perfectly URL-encoded
                        if "allorigins" in proxy:
                            target_url = proxy + urllib.parse.quote(base_url)
                        else:
                            target_url = proxy + base_url
                            
                        req = urllib.request.Request(target_url, headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                        })
                        
                        with urllib.request.urlopen(req, timeout=15) as response:
                            response_text = response.read().decode('utf-8')
                            
                            # A successful connection to Twitter returns the __NEXT_DATA__ JSON payload
                            if '__NEXT_DATA__' in response_text:
                                html = response_text
                                connection_type = 'Proxy Wrapper' if proxy else 'Direct Connection'
                                print(f"Successfully connected to Syndication API via {connection_type}.")
                                break
                    except Exception as proxy_err:
                        continue  # Silently skip to the next proxy node
                
                if html:
                    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
                    if match:
                        syndication_data = json.loads(match.group(1))
                        
                        def extract_syndication_tweets(obj):
                            if isinstance(obj, dict):
                                if 'text' in obj and 'created_at' in obj and 'id_str' in obj:
                                    author = obj.get('user', {}).get('screen_name', '')
                                    if not author or author.lower() == username.lower():
                                        tweets.append({
                                            'text': obj.get('full_text') or obj.get('text', ''),
                                            'created_at': obj.get('created_at', '')
                                        })
                                for k, v in obj.items():
                                    extract_syndication_tweets(v)
                            elif isinstance(obj, list):
                                for item in obj:
                                    extract_syndication_tweets(item)
                                    
                        extract_syndication_tweets(syndication_data)
                        
                        if tweets:
                            seen_texts = set()
                            unique_tweets = []
                            for t in tweets:
                                if t['text'] not in seen_texts:
                                    seen_texts.add(t['text'])
                                    unique_tweets.append(t)
                            tweets = unique_tweets
                            print(f"Successfully retrieved {len(tweets)} tweets via Syndication fallback for {username}!")
                else:
                    print(f"All Syndication endpoints (including proxy rotators) failed to bypass the 429 rate limit for {username}.")
            except Exception as e:
                print(f"Syndication fallback encountered a critical error for {username}: {e}")
        # --- END FALLBACK LOGIC ---

        if not tweets:
            print(f"No tweets found via Scraper or Proxy Fallbacks for {username}.")
            continue

        count = 0
        for tweet in tweets:
            if count >= 5: 
                break
            content = tweet.get("text", "").strip()
            if not content:
                continue 

            # --- DATA SANITIZATION ---
            content = re.sub(r"^BREAKING:\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"^UPDATE:\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"^EXCLUSIVE:\s*", "", content, flags=re.IGNORECASE)
            
            content = re.sub(r"🔴\s*More on", "", content, flags=re.IGNORECASE)
            content = re.sub(r"🔴\s*LIVE updates:", "", content, flags=re.IGNORECASE)
            content = re.sub(r"Here's what we know\.", "", content, flags=re.IGNORECASE)
            
            content = re.sub(r"\s*For more on this and other news visit.*$", "", content, flags=re.IGNORECASE)
            content = re.sub(r"Watch:", "", content, flags=re.IGNORECASE)
            content = re.sub(r"🔊", "", content)
            
            content = re.sub(r"[^.!?\n]*(?:reuters[^.!?\n]*podcast|podcast[^.!?\n]*reuters)[^.!?\n]*[.!?\n]*", "", content, flags=re.IGNORECASE)
            
            content = re.sub(r"https?://\S+|www\.\S+", "", content)
            content = re.sub(r"co/[a-zA-Z0-9]+", "", content)
            content = re.sub(r"#\w+", "", content)

            content = re.sub(
                r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\u200d\ufe0f\U0001F1E6-\U0001F1FF\u20e3]",
                "",
                content
            )

            content = re.sub(r"\s+", " ", content).strip()

            if not content:
                continue 
            
            word_count = len(content.split())
            if word_count <= 2 or word_count > 400:
                continue
            
            if not content.endswith(('.', '!', '?')):
                content += '.'

            # --- EXTRACT DATE FOR SORTING ---
            date_str = tweet.get("created_at") or tweet.get("date") or ""
            parsed_date = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
            
            if date_str:
                try:
                    dt = parsedate_to_datetime(date_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    parsed_date = dt
                except Exception:
                    try:
                        dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=datetime.timezone.utc)
                        parsed_date = dt
                    except Exception:
                        pass

            all_extracted_tweets.append((parsed_date, content))
            count += 1

    if not all_extracted_tweets:
        print("No tweet data was gathered. Review the Scraper Logs above to see why X blocked the extraction.")
        return

    all_extracted_tweets.sort(key=lambda x: x[0], reverse=True)
    all_rows_to_write = [[t[1]] for t in all_extracted_tweets]

    # 3. Connect and update Google Sheet
    max_retries = 10
    for attempt in range(max_retries):
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
            try:
                worksheet = sh.worksheet("News")
            except gspread.exceptions.WorksheetNotFound:
                print("Creating worksheet 'News'...")
                worksheet = sh.add_worksheet(title="News", rows="100", cols="5")

            print(f"Clearing old content in worksheet '{worksheet.title}'...")
            worksheet.clear()

            print(f"Writing {len(all_rows_to_write)} records to worksheet '{worksheet.title}'...")
            worksheet.update(range_name='A1', values=all_rows_to_write)

            print("Applying clean table formatting and auto-resizing columns...")
            try:
                worksheet.format('A:A', {'wrapStrategy': 'WRAP'})
            except Exception as format_err:
                print(f"Word wrapping failed: {format_err}")

            try:
                worksheet.columns_auto_resize(0, 1)
            except Exception as resize_err:
                print(f"Auto-resizing failed: {resize_err}")

            print("News sheet updated successfully.")
            break 

        except Exception as e:
            error_message = str(e)
            if "429" in error_message or "Quota exceeded" in error_message or "rateLimitExceeded" in error_message:
                if attempt < max_retries - 1:
                    print(f"Rate limit exceeded (429). Retrying in 10 seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(10)
                else:
                    print(f"Failed to write to Google Sheet after {max_retries} attempts: {e}")
            else:
                print(f"Failed to write to Google Sheet: {e}")
                break

if __name__ == "__main__":
    accounts = [
        {"username": "Reuters", "display_name": "Reuters"},
        {"username": "AP", "display_name": "The Associated Press"},
        {"username": "AJENews", "display_name": "Al Jazeera Breaking News"}
    ]

    ensure_config_file(max_tweets=15)
    patch_scraper_source()
    clean_and_move_cookies()
    success = scrape_all_accounts(accounts)
    
    if success:
        update_google_sheet_with_tweets(accounts)
