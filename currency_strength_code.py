import json
import os
import sys
import time
import numpy as np
import pandas as pd
import yfinance as yf
import gspread


def get_gspread_client():
    """Authenticates gspread using GitHub Secrets environment variable (GCP_CREDENTIALS)
    or falls back to a local JSON file path.
    """
    service_account_env = os.environ.get("GCP_CREDENTIALS") or os.environ.get("GCP_SERVICE_ACCOUNT")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    if service_account_env:
        creds_dict = json.loads(service_account_env)
        return gspread.service_account_from_dict(creds_dict, scopes=scopes)
    else:
        # Fallback for Google Colab / Local Environment
        service_account_file = "/content/forexdailybias-5ce3a8ede6c9.json"
        if os.path.exists(service_account_file):
            return gspread.service_account(filename=service_account_file, scopes=scopes)
        elif os.path.exists("forexdailybias-5ce3a8ede6c9.json"):
            return gspread.service_account(filename="forexdailybias-5ce3a8ede6c9.json", scopes=scopes)
        else:
            raise FileNotFoundError("Service account key not found.")


def calculate_csm_for_row(current_row, previous_row):
    """Calculates the strength score for each of the 8 major currencies using an O(N) log-return optimization."""
    currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]

    # 1. Reconstruct the price of 1 unit of each currency in USD terms
    prices_now = {
        "USD": 1.0,
        "EUR": float(current_row["EURUSD=X"]),
        "GBP": float(current_row["GBPUSD=X"]),
        "AUD": float(current_row["AUDUSD=X"]),
        "NZD": float(current_row["NZDUSD=X"]),
        "CAD": 1.0 / float(current_row["USDCAD=X"]),
        "CHF": 1.0 / float(current_row["USDCHF=X"]),
        "JPY": 1.0 / float(current_row["USDJPY=X"]),
    }

    prices_prev = {
        "USD": 1.0,
        "EUR": float(previous_row["EURUSD=X"]),
        "GBP": float(previous_row["GBPUSD=X"]),
        "AUD": float(previous_row["AUDUSD=X"]),
        "NZD": float(previous_row["NZDUSD=X"]),
        "CAD": 1.0 / float(previous_row["USDCAD=X"]),
        "CHF": 1.0 / float(previous_row["USDCHF=X"]),
        "JPY": 1.0 / float(previous_row["USDJPY=X"]),
    }

    # 2. Calculate log returns for each currency against the USD
    log_returns = {}
    for c in currencies:
        log_returns[c] = np.log(prices_now[c] / prices_prev[c]) * 100

    sum_all_returns = sum(log_returns.values())

    # 3. Apply mathematical simplification to deduce average cross-strength
    normalized_scores = {}
    for c in currencies:
        # Mathematically equivalent to averaging the log-returns of all 7 cross pairs
        score = (8 * log_returns[c] - sum_all_returns) / 7.0
        normalized_scores[c] = round(score, 4)

    return normalized_scores


def fetch_and_clean_data(usd_tickers, period="3mo"):
    """Downloads historical daily data. We only need daily data to construct all timeframes."""
    print("Fetching historical daily rates from Yahoo Finance...")
    data = yf.download(usd_tickers, period=period, interval="1d", auto_adjust=True)

    if data.empty:
        raise ValueError("Failed to retrieve data from Yahoo Finance.")

    close_df = data["Close"] if "Close" in data else data["close"] if "close" in data else data

    # Clean data avoiding weekend gaps
    close_df = close_df.dropna(how="all").ffill().dropna()

    if len(close_df) < 25:
        raise ValueError("Insufficient data returned to calculate monthly momentum. Try again later.")

    return close_df


def process_timeframe_metrics(close_df, lookback, label):
    """Calculates metrics dynamically based on 'lookback' trading days ensuring perfect symmetry."""
    
    # Symmetrical indexing:
    # Today's momentum = Today vs N days ago
    row_today = close_df.iloc[-1]
    row_today_prev = close_df.iloc[-1 - lookback]
    
    # Yesterday's momentum = Yesterday vs (N+1) days ago
    row_yesterday = close_df.iloc[-2]
    row_yesterday_prev = close_df.iloc[-2 - lookback]

    strength_today = calculate_csm_for_row(row_today, row_today_prev)
    strength_yesterday = calculate_csm_for_row(row_yesterday, row_yesterday_prev)

    report_data = []
    for cur in strength_today:
        today_val = strength_today[cur]
        yest_val = strength_yesterday[cur]

        abs_change = today_val - yest_val
        
        # Note: Pct change of a zero-centered log return is volatile, but kept for spreadsheet compatibility
        pct_change = ((abs_change / abs(yest_val)) * 100 if yest_val != 0 else 0.0)

        report_data.append({
            "Currency": cur,
            "Today": today_val,
            "Yesterday": yest_val,
            "Abs Change": abs_change,
            "Pct Change": pct_change,
        })

    report_df = pd.DataFrame(report_data)
    
    # Filter and sort
    target_currencies = ["USD", "EUR", "GBP", "JPY"]
    report_df = report_df[report_df["Currency"].isin(target_currencies)]
    report_df = report_df.sort_values(by="Today", ascending=False).reset_index(drop=True)

    print("\n" + "=" * 80)
    print(f"               {label.upper()} FOREX CURRENCY STRENGTH & MOMENTUM REPORT")
    print("=" * 80)
    print(f"{'Currency':<10} | {'Today':<12} | {'Yesterday':<12} | {'Point Change':<15} | {'% Change':<12}")
    print("-" * 80)

    for _, row in report_df.iterrows():
        print(f"{row['Currency']:<10} | {row['Today']:+11.3f}% | {row['Yesterday']:+11.3f}% | {row['Abs Change']:+14.3f}% | {row['Pct Change']:+11.2f}%")
    print("=" * 80)

    # Re-map row data for Google Sheets update
    report_df["Rank"] = range(1, len(report_df) + 1)
    metrics_by_currency = {
        row["Currency"]: [
            int(row["Rank"]),
            round(float(row["Today"]), 4),
            round(float(row["Yesterday"]), 4),
            round(float(row["Abs Change"]), 4),
            round(float(row["Pct Change"]), 2),
        ]
        for _, row in report_df.iterrows()
    }

    # Order rows exactly as Google Sheet expects them: USD, EUR, GBP, JPY
    sheet_currencies = ["USD", "EUR", "GBP", "JPY"]
    rows_to_update = [metrics_by_currency[cur] for cur in sheet_currencies]

    return rows_to_update


def batch_update_with_retry(worksheet, data, max_attempts=10):
    """Updates Google Sheets in a single batch with exponential backoff retry logic for 429 API errors."""
    for attempt in range(1, max_attempts + 1):
        try:
            worksheet.batch_update(data)
            return  # Success, exit the loop
        except Exception as e:
            # If we hit a 429 error and haven't exhausted attempts, sleep and retry
            if "429" in str(e) and attempt < max_attempts:
                sleep_time = 2 ** attempt  # Exponential backoff (2s, 4s, 8s, 16s...)
                print(f"[Warning] API Rate limit (429) exceeded for batch update. Retrying in {sleep_time} seconds (Attempt {attempt}/{max_attempts})...")
                time.sleep(sleep_time)
            else:
                # Reraise the exception if it's not a 429 or if we've exhausted our max attempts
                raise e


def generate_daily_report():
    usd_tickers = [
        "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X",
        "USDCAD=X", "USDCHF=X", "USDJPY=X"
    ]

    # Fetch a ~3-month pool of daily data ONCE (faster and fixes timeframe asymmetry)
    daily_close_df = fetch_and_clean_data(usd_tickers, period="3mo")
    
    # Lookbacks reflect standard trading days: Daily(1), Weekly(5), Monthly(21)
    daily_rows = process_timeframe_metrics(daily_close_df, lookback=1, label="Daily")
    weekly_rows = process_timeframe_metrics(daily_close_df, lookback=5, label="Weekly")
    monthly_rows = process_timeframe_metrics(daily_close_df, lookback=21, label="Monthly")

    # Authenticate via helper function
    gc = get_gspread_client()
    spreadsheet_id = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
    sh = gc.open_by_key(spreadsheet_id)
    worksheet = sh.sheet1

    # Bundle all updates into a single list of dictionaries
    batch_data = [
        {'range': 'L38:P41', 'values': daily_rows},
        {'range': 'R38:V41', 'values': weekly_rows},
        {'range': 'X38:AB41', 'values': monthly_rows}
    ]

    # Execute a single API call for all ranges
    batch_update_with_retry(worksheet, data=batch_data)

    print("\nSuccessfully updated Daily Currency Ranks & Metrics in Google Spreadsheet (cells L38:P41).")
    print("Successfully updated Weekly Currency Ranks & Metrics in Google Spreadsheet (cells R38:V41).")
    print("Successfully updated Monthly Currency Ranks & Metrics in Google Spreadsheet (cells X38:AB41).")


if __name__ == "__main__":
    try:
        generate_daily_report()
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Execution failed: {e}")
        sys.exit(1)
