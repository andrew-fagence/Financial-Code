import os
import time
import requests
import json
import gspread
from datetime import datetime, timezone

# ==========================================
# GOOGLE SHEETS AUTHENTICATION
# ==========================================

# Read the JSON credentials from the GitHub Actions environment variable
credentials_json = os.environ.get("GCP_CREDENTIALS")

if not credentials_json:
    raise ValueError("No GCP_CREDENTIALS environment variable found. Make sure the GitHub secret is set and mapped.")

# Load the credentials into a dictionary and authorize gspread
creds_dict = json.loads(credentials_json)
gc = gspread.service_account_from_dict(creds_dict)

# Open the Google Sheet by ID and select the specific tab
SPREADSHEET_ID = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
WORKSHEET_NAME = "Sheet1"

# Initialize 'wb' (the worksheet object used throughout the rest of your code)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)
wb = spreadsheet.worksheet(WORKSHEET_NAME)

# ==========================================
# GOOGLE SHEETS RETRY HELPERS
# ==========================================

def read_cell_with_retry(worksheet, row, col, max_retries=10):
    """Reads a cell value with exponential backoff for API limits."""
    delay = 5
    for attempt in range(max_retries):
        try:
            val = worksheet.cell(row, col).value
            time.sleep(0.5)  # Pace the requests to avoid hitting burst limits
            return val
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Read error at row {row}, col {col}: {e}. Retrying in {delay}s...")
            time.sleep(delay)
            # Cap the max delay to 60 seconds to wait out the per-minute quota
            delay = min(delay * 2, 60)

def update_cell_with_retry(worksheet, row, col, value, max_retries=10):
    """Updates a cell value with exponential backoff for API limits."""
    delay = 5
    for attempt in range(max_retries):
        try:
            worksheet.update_cell(row, col, value)
            time.sleep(0.5)  # Pace the requests to avoid hitting burst limits
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Write error at row {row}, col {col}: {e}. Retrying in {delay}s...")
            time.sleep(delay)
            # Cap the max delay to 60 seconds to wait out the per-minute quota
            delay = min(delay * 2, 60)

def batch_update_with_retry(worksheet, data, max_retries=10):
    """Executes a batch update with exponential backoff for API limits."""
    if not data:
        return
    delay = 5
    for attempt in range(max_retries):
        try:
            worksheet.batch_update(data)
            time.sleep(0.5)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Batch write error: {e}. Retrying in {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, 60)

# Initialize a list to hold all of our batch updates
batch_updates = []

# ==========================================
# FIND THE NEXT ACTIVE FED DECISION MARKET
# ==========================================

def find_next_fed_event():

    url = "https://gamma-api.polymarket.com/public-search"

    params = {
        "q": "Fed Decision",
        "limit": 100
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    events = data.get("events", [])

    fed_events = []

    for event in events:

        title = event.get("title", "")
        active = event.get("active", False)
        closed = event.get("closed", False)

        if (
            title.startswith("Fed Decision in ")
            and title.endswith("?")
            and active
            and not closed
        ):
            fed_events.append(event)

    if not fed_events:
        return None

    # Sort by closing date
    def get_end_date(event):

        date_string = event.get("endDate")

        if not date_string:
            return datetime.max.replace(tzinfo=timezone.utc)

        try:
            return datetime.fromisoformat(
                date_string.replace("Z", "+00:00")
            )
        except:
            return datetime.max.replace(tzinfo=timezone.utc)

    fed_events.sort(key=get_end_date)

    return fed_events[0]


# ==========================================
# GET ODDS
# ==========================================

def get_event_odds(event):

    slug = event["slug"]

    response = requests.get(
        "https://gamma-api.polymarket.com/events",
        params={"slug": slug},
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        return []

    full_event = data[0]

    results = []

    for market in full_event.get("markets", []):

        label = market.get("groupItemTitle")

        prices = market.get("outcomePrices")

        if isinstance(prices, str):
            prices = json.loads(prices)

        if not prices:
            continue

        yes_probability = float(prices[0]) * 100

        results.append({
            "label": label,
            "probability": yes_probability
        })

    return results


# ==========================================
# RUN ONCE
# ==========================================

event = find_next_fed_event()

if event is None:

    print("No active Fed Decision market found.")

else:

    odds = get_event_odds(event)

    # Convert odds into a dictionary
    odds_dict = {
        item["label"]: item["probability"]
        for item in odds
    }

    # Calculate combined odds
    rate_cut_odds = (
        odds_dict.get("50+ bps decrease", 0)
        + odds_dict.get("25 bps decrease", 0)
    )

    rate_hike_odds = (
        odds_dict.get("25 bps increase", 0)
        + odds_dict.get("50+ bps increase", 0)
    )

    print("=" * 65)
    print(event["title"])
    print("=" * 65)

    print(f"Market closes: {event.get('endDate')}")
    print()

    print(f"{'Rate Cut Odds':<30}{rate_cut_odds:>7.2f}%")
    print(f"{'No change':<30}{odds_dict.get('No change', 0):>7.2f}%")
    print(f"{'Rate Hike Odds':<30}{rate_hike_odds:>7.2f}%")

    print("=" * 65)


    # ==========================================
    # QUEUE NEW FED ODDS FOR BATCH UPDATE
    # ==========================================
    # Row 160: Col B (Hike), Col C (Hold), Col D (Cut)
    batch_updates.append({
        "range": "B160:D160",
        "values": [[
            round(rate_hike_odds, 2),
            round(odds_dict.get("No change", 0), 2),
            round(rate_cut_odds, 2)
        ]]
    })
    print("Fed odds queued for batch update.")


# ==========================================
# BLOCK 2: ECB INTEREST RATES
# ==========================================

def find_next_ecb_event():
    url = "https://gamma-api.polymarket.com/public-search"
    params = {"q": "ECB Interest Rates", "limit": 100}

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    events = data.get("events", [])

    ecb_events = []

    for event in events:
        title = event.get("title", "")
        active = event.get("active", False)
        closed = event.get("closed", False)

        if (
            title.startswith("ECB Interest Rates:")
            and active
            and not closed
        ):
            ecb_events.append(event)

    if not ecb_events:
        return None

    def get_end_date(event):
        date_string = event.get("endDate")

        if not date_string:
            return datetime.max.replace(tzinfo=timezone.utc)

        try:
            return datetime.fromisoformat(
                date_string.replace("Z", "+00:00")
            )
        except:
            return datetime.max.replace(tzinfo=timezone.utc)

    ecb_events.sort(key=get_end_date)

    return ecb_events[0]


def get_ecb_odds(event):
    slug = event["slug"]

    response = requests.get(
        "https://gamma-api.polymarket.com/events",
        params={"slug": slug},
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        return []

    full_event = data[0]

    results = []

    for market in full_event.get("markets", []):
        label = market.get("groupItemTitle")
        prices = market.get("outcomePrices")

        if isinstance(prices, str):
            prices = json.loads(prices)

        if not prices:
            continue

        yes_probability = float(prices[0]) * 100

        results.append({
            "label": label,
            "probability": yes_probability
        })

    return results


# ---------------------------------------------------------
# FIND NEXT ECB MEETING
# ---------------------------------------------------------

event = find_next_ecb_event()

if event is None:
    print("No active ECB Interest Rates market found.")

else:
    odds = get_ecb_odds(event)

    odds_dict = {
        item["label"]: item["probability"]
        for item in odds
    }

    # -----------------------------------------------------
    # CALCULATE ECB ODDS
    # -----------------------------------------------------

    rate_cut_odds = (
        odds_dict.get("50+ bps decrease", 0)
        + odds_dict.get("25 bps decrease", 0)
    )

    rate_hike_odds = (
        odds_dict.get("25 bps increase", 0)
        + odds_dict.get("50+ bps increase", 0)
    )

    rate_hold_odds = odds_dict.get("No change", 0)

    # -----------------------------------------------------
    # DISPLAY
    # -----------------------------------------------------

    print("=" * 65)
    print(event["title"])
    print("=" * 65)

    print(f"Market closes: {event.get('endDate')}")
    print()

    print(f"{'ECB Rate Hike Odds':<30}{rate_hike_odds:>7.2f}%")
    print(f"{'ECB Rate Hold Odds':<30}{rate_hold_odds:>7.2f}%")
    print(f"{'ECB Rate Cut Odds':<30}{rate_cut_odds:>7.2f}%")

    print("=" * 65)

    # -----------------------------------------------------
    # GOOGLE SHEETS
    # ROW 161 = ECB
    # -----------------------------------------------------

    batch_updates.append({
        "range": "B161:D161",
        "values": [[
            round(rate_hike_odds, 6),
            round(rate_hold_odds, 6),
            round(rate_cut_odds, 6)
        ]]
    })
    print("ECB odds queued for batch update.")


# ==========================================
# BLOCK 3: BANK OF ENGLAND DECISION
# ==========================================

def find_next_boe_event():
    url = "https://gamma-api.polymarket.com/public-search"
    params = {"q": "Bank of England decision", "limit": 100}

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    events = data.get("events", [])

    boe_events = []

    for event in events:
        title = event.get("title", "")
        active = event.get("active", False)
        closed = event.get("closed", False)

        if (
            title.startswith("Bank of England decision in ")
            and active
            and not closed
        ):
            boe_events.append(event)

    if not boe_events:
        return None

    def get_end_date(event):
        date_string = event.get("endDate")

        if not date_string:
            return datetime.max.replace(tzinfo=timezone.utc)

        try:
            return datetime.fromisoformat(
                date_string.replace("Z", "+00:00")
            )
        except:
            return datetime.max.replace(tzinfo=timezone.utc)

    boe_events.sort(key=get_end_date)

    return boe_events[0]


def get_boe_odds(event):
    slug = event["slug"]

    response = requests.get(
        "https://gamma-api.polymarket.com/events",
        params={"slug": slug},
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        return []

    full_event = data[0]

    results = []

    for market in full_event.get("markets", []):
        label = market.get("groupItemTitle")
        prices = market.get("outcomePrices")

        if isinstance(prices, str):
            prices = json.loads(prices)

        if not prices:
            continue

        yes_probability = float(prices[0]) * 100

        results.append({
            "label": label,
            "probability": yes_probability
        })

    return results


# ---------------------------------------------------------
# FIND NEXT BANK OF ENGLAND MEETING
# ---------------------------------------------------------

event = find_next_boe_event()

if event is None:
    print("No active Bank of England decision market found.")

else:
    odds = get_boe_odds(event)

    odds_dict = {
        item["label"]: item["probability"]
        for item in odds
    }

    # -----------------------------------------------------
    # CALCULATE BOE ODDS
    # -----------------------------------------------------

    rate_cut_odds = (
        odds_dict.get("50+ bps decrease", 0)
        + odds_dict.get("25 bps decrease", 0)
    )

    rate_hike_odds = (
        odds_dict.get("25 bps increase", 0)
        + odds_dict.get("50+ bps increase", 0)
    )

    rate_hold_odds = odds_dict.get("No change", 0)

    # -----------------------------------------------------
    # DISPLAY
    # -----------------------------------------------------

    print("=" * 65)
    print(event["title"])
    print("=" * 65)

    print(f"Market closes: {event.get('endDate')}")
    print()

    print(f"{'Bank of England Rate Hike Odds':<30}{rate_hike_odds:>7.2f}%")
    print(f"{'Bank of England Rate Hold Odds':<30}{rate_hold_odds:>7.2f}%")
    print(f"{'Bank of England Rate Cut Odds':<30}{rate_cut_odds:>7.2f}%")

    print("=" * 65)

    # -----------------------------------------------------
    # GOOGLE SHEETS
    # ROW 162 = BANK OF ENGLAND
    # -----------------------------------------------------
    
    batch_updates.append({
        "range": "B162:D162",
        "values": [[
            round(rate_hike_odds, 6),
            round(rate_hold_odds, 6),
            round(rate_cut_odds, 6)
        ]]
    })
    print("Bank of England odds queued for batch update.")


# ==========================================
# BLOCK 4: BANK OF JAPAN DECISION
# ==========================================

def find_next_boj_event():
    url = "https://gamma-api.polymarket.com/public-search"
    params = {"q": "Bank of Japan Decision", "limit": 100}

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    events = data.get("events", [])

    boj_events = []

    for event in events:
        title = event.get("title", "")
        active = event.get("active", False)
        closed = event.get("closed", False)

        if (
            title.startswith("Bank of Japan Decision in ")
            and active
            and not closed
        ):
            boj_events.append(event)

    if not boj_events:
        return None

    def get_end_date(event):
        date_string = event.get("endDate")

        if not date_string:
            return datetime.max.replace(tzinfo=timezone.utc)

        try:
            return datetime.fromisoformat(
                date_string.replace("Z", "+00:00")
            )
        except:
            return datetime.max.replace(tzinfo=timezone.utc)

    boj_events.sort(key=get_end_date)

    return boj_events[0]


def get_boj_odds(event):
    slug = event["slug"]

    response = requests.get(
        "https://gamma-api.polymarket.com/events",
        params={"slug": slug},
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        return []

    full_event = data[0]

    results = []

    for market in full_event.get("markets", []):
        label = market.get("groupItemTitle")
        prices = market.get("outcomePrices")

        if isinstance(prices, str):
            prices = json.loads(prices)

        if not prices:
            continue

        yes_probability = float(prices[0]) * 100

        results.append({
            "label": label,
            "probability": yes_probability
        })

    return results


# ---------------------------------------------------------
# FIND NEXT BANK OF JAPAN MEETING
# ---------------------------------------------------------

event = find_next_boj_event()

if event is None:
    print("No active Bank of Japan decision market found.")

else:
    odds = get_boj_odds(event)

    odds_dict = {
        item["label"]: item["probability"]
        for item in odds
    }

    # -----------------------------------------------------
    # CALCULATE BOJ ODDS
    # -----------------------------------------------------

    rate_cut_odds = (
        odds_dict.get("50+ bps decrease", 0)
        + odds_dict.get("25 bps decrease", 0)
    )

    rate_hike_odds = (
        odds_dict.get("25 bps increase", 0)
        + odds_dict.get("50+ bps increase", 0)
    )

    rate_hold_odds = odds_dict.get("No change", 0)

    # -----------------------------------------------------
    # DISPLAY
    # -----------------------------------------------------

    print("=" * 65)
    print(event["title"])
    print("=" * 65)

    print(f"Market closes: {event.get('endDate')}")
    print()

    print(f"{'Bank of Japan Rate Hike Odds':<30}{rate_hike_odds:>7.2f}%")
    print(f"{'Bank of Japan Rate Hold Odds':<30}{rate_hold_odds:>7.2f}%")
    print(f"{'Bank of Japan Rate Cut Odds':<30}{rate_cut_odds:>7.2f}%")

    print("=" * 65)

    # -----------------------------------------------------
    # GOOGLE SHEETS
    # ROW 163 = BANK OF JAPAN
    # -----------------------------------------------------
    
    batch_updates.append({
        "range": "B163:D163",
        "values": [[
            round(rate_hike_odds, 6),
            round(rate_hold_odds, 6),
            round(rate_cut_odds, 6)
        ]]
    })
    print("Bank of Japan odds queued for batch update.")


# ==========================================
# EXECUTE THE BATCH UPDATE
# ==========================================

if batch_updates:
    batch_update_with_retry(wb, batch_updates)
    print("\nAll queued odds have been batch updated to Google Sheets successfully.")
else:
    print("\nNo odds were found to update.")
