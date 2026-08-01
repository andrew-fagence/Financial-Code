import json
import os
import sys
import numpy as np
import pandas as pd
import yfinance as yf
import gspread


def get_gspread_client():
    """Authenticates gspread using GitHub Secrets environment variable

    or falls back to a local JSON file path.
    """
    service_account_env = os.environ.get("GCP_CREDENTIALS")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    if service_account_env:
        # Running in GitHub Actions
        creds_dict = json.loads(service_account_env)
        return gspread.service_account_from_dict(creds_dict, scopes=scopes)
    else:
        # Fallback for Google Colab / Local Environment
        service_account_file = "/content/forexdailybias-5ce3a8ede6c9.json"
        if os.path.exists(service_account_file):
            return gspread.service_account(
                filename=service_account_file, scopes=scopes
            )
        elif os.path.exists("forexdailybias-5ce3a8ede6c9.json"):
            return gspread.service_account(
                filename="forexdailybias-5ce3a8ede6c9.json", scopes=scopes
            )
        else:
            raise FileNotFoundError(
                "Service account key not found in GCP_CREDENTIALS environment variable or local file."
            )


def calculate_csm_for_row(current_row, previous_row):
    """Calculates the strength score for each of the 8 major currencies

    comparing a current price row with a previous reference row.
    Uses Logarithmic Returns for perfect symmetry and mathematical accuracy.
    """
    currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]

    # Reconstruct the price of 1 unit of each currency in USD terms
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

    strength_scores = {c: 0.0 for c in currencies}

    # Reconstruct all 28 crosses and calculate log return
    for i in range(len(currencies)):
        for j in range(i + 1, len(currencies)):
            base = currencies[i]
            quote = currencies[j]

            # Cross rate = Base Price in USD / Quote Price in USD
            rate_now = prices_now[base] / prices_now[quote]
            rate_prev = prices_prev[base] / prices_prev[quote]

            # Log Return calculation
            log_change = np.log(rate_now / rate_prev) * 100

            # Add to base currency, subtract from quote currency
            strength_scores[base] += log_change
            strength_scores[quote] -= log_change

    # Normalize by the number of counterparts (N-1 = 7)
    normalized_scores = {
        c: round(score / 7.0, 4) for c, score in strength_scores.items()
    }
    return normalized_scores


def fetch_and_clean_data(usd_tickers, period, interval, label):
    """Downloads historical ticker data and cleans missing/invalid entries."""
    print(f"Fetching historical {label.lower()} rates from Yahoo Finance...")
    data = yf.download(
        usd_tickers, period=period, interval=interval, auto_adjust=True
    )

    if data.empty:
        raise ValueError(
            f"Failed to retrieve {label.lower()} data from Yahoo Finance."
        )

    close_df = (
        data["Close"]
        if "Close" in data
        else data["close"] if "close" in data else data
    )

    close_df = close_df.dropna(how="all")
    close_df = close_df.ffill()
    close_df = close_df.dropna()

    if len(close_df) < 3:
        raise ValueError(
            f"Insufficient {label.lower()} data returned to calculate momentum. Try again later."
        )

    return close_df


def process_timeframe_metrics(close_df, label):
    """Calculates CSM scores, formats report, and prepares rows for Google Sheet update."""
    row_today = close_df.iloc[-1]
    row_yesterday = close_df.iloc[-2]
    row_day_before = close_df.iloc[-3]

    strength_today = calculate_csm_for_row(row_today, row_yesterday)
    strength_yesterday = calculate_csm_for_row(row_yesterday, row_day_before)

    report_data = []
    for cur in strength_today:
        today_val = strength_today[cur]
        yest_val = strength_yesterday[cur]

        abs_change = today_val - yest_val
        pct_change = (
            (abs_change / abs(yest_val)) * 100 if yest_val != 0 else 0.0
        )

        report_data.append({
            "Currency": cur,
            "Today": today_val,
            "Yesterday": yest_val,
            "Abs Change": abs_change,
            "Pct Change": pct_change,
        })

    report_df = pd.DataFrame(report_data)
    target_currencies = ["USD", "EUR", "GBP", "JPY"]
    report_df = report_df[report_df["Currency"].isin(target_currencies)]
    report_df = report_df.sort_values(
        by="Today", ascending=False
    ).reset_index(drop=True)

    print("\n" + "=" * 80)
    print(
        f"               {label.upper()} FOREX CURRENCY STRENGTH & MOMENTUM"
        " REPORT"
    )
    print(
        f"               Run time: {close_df.index[-1].strftime('%Y-%m-%d')}"
        " 08:00 AM"
    )
    print("=" * 80)
    print(
        f"{'Currency':<10} | {'Today':<12} | {'Yesterday':<12} |"
        f" {'Point Change':<15} | {'% Change':<12}"
    )
    print("-" * 80)

    for _, row in report_df.iterrows():
        print(
            f"{row['Currency']:<10} | "
            f"{row['Today']:+11.3f}% | "
            f"{row['Yesterday']:+11.3f}% | "
            f"{row['Abs Change']:+14.3f}% | "
            f"{row['Pct Change']:+11.2f}%"
        )
    print("=" * 80)

    report_df["Rank"] = range(1, len(report_df) + 1)

    metrics_by_currency = {}
    for _, row in report_df.iterrows():
        metrics_by_currency[row["Currency"]] = [
            int(row["Rank"]),
            round(float(row["Today"]), 4),
            round(float(row["Yesterday"]), 4),
            round(float(row["Abs Change"]), 4),
            round(float(row["Pct Change"]), 2),
        ]

    sheet_currencies = ["USD", "EUR", "GBP", "JPY"]
    rows_to_update = [metrics_by_currency[cur] for cur in sheet_currencies]

    return rows_to_update


def generate_daily_report():
    usd_tickers = [
        "EURUSD=X",
        "GBPUSD=X",
        "AUDUSD=X",
        "NZDUSD=X",
        "USDCAD=X",
        "USDCHF=X",
        "USDJPY=X",
    ]

    daily_close_df = fetch_and_clean_data(
        usd_tickers, period="10d", interval="1d", label="Daily"
    )
    daily_rows = process_timeframe_metrics(daily_close_df, label="Daily")

    weekly_close_df = fetch_and_clean_data(
        usd_tickers, period="3mo", interval="1wk", label="Weekly"
    )
    weekly_rows = process_timeframe_metrics(weekly_close_df, label="Weekly")

    monthly_close_df = fetch_and_clean_data(
        usd_tickers, period="1y", interval="1mo", label="Monthly"
    )
    monthly_rows = process_timeframe_metrics(monthly_close_df, label="Monthly")

    # Authenticate via helper function
    gc = get_gspread_client()

    spreadsheet_id = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
    sh = gc.open_by_key(spreadsheet_id)

    # Uses the first sheet in the spreadsheet
    worksheet = sh.sheet1

    # Update Daily range L38:P41
    worksheet.update(range_name="L38:P41", values=daily_rows)
    print(
        "\nSuccessfully updated Daily Currency Ranks & Metrics in Google"
        " Spreadsheet (cells L38:P41)."
    )

    # Update Weekly range R38:V41
    worksheet.update(range_name="R38:V41", values=weekly_rows)
    print(
        "Successfully updated Weekly Currency Ranks & Metrics in Google"
        " Spreadsheet (cells R38:V41)."
    )

    # Update Monthly range X38:AB41
    worksheet.update(range_name="X38:AB41", values=monthly_rows)
    print(
        "Successfully updated Monthly Currency Ranks & Metrics in Google"
        " Spreadsheet (cells X38:AB41)."
    )


if __name__ == "__main__":
    try:
        generate_daily_report()
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Execution failed: {e}")
        # Explicitly exit with error code 1 so GitHub Actions reports failure if an error occurs
        sys.exit(1)
