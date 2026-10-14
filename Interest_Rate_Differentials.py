# install libraries (Managed by GitHub Actions YAML)
import time
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

def retry_api_call(func, *args, **kwargs):
    """Wait/Retry block with exponential backoff in case of API/Quota limit errors."""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"API call failed: {e}. Retrying in {2 ** attempt} seconds...")
            time.sleep(2 ** attempt)

scopes = [
    "https://www.googleapis.com/auth/spreadsheets"
]

# get credentials from JSON file
creds = Credentials.from_service_account_file("forexdailybias-5ce3a8ede6c9.json", scopes=scopes)
client = gspread.authorize(creds)

# ID of google sheet workbook
sheet_id = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
sheet = retry_api_call(client.open_by_key, sheet_id)

# get and print row headings for testing
values_list = retry_api_call(sheet.sheet1.row_values, 1)
print(values_list)

# Define wb to reference sheet1 (referenced later in the script)
wb = sheet.sheet1

# Get Interest Rates

# USA (upper limit)
def get_us_interest_rate():
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARU"
    df = pd.read_csv(url)
    df["DFEDTARU"] = pd.to_numeric(df["DFEDTARU"], errors="coerce")
    return float(df["DFEDTARU"].dropna().iloc[-1])

USArate = retry_api_call(get_us_interest_rate)
print(f"US Fed upper interest rate: {USArate:.2f}%")

# EUR Rate
EURrate = float(retry_api_call(wb.cell, 36, 8).value)
print(EURrate)

# GBP Rate
GBPrate = float(retry_api_call(wb.cell, 38, 8).value)
print(GBPrate)

# JPY Rate
JPYrate = float(retry_api_call(wb.cell, 34, 11).value)
print(JPYrate)


##############################################################################
############################### USA ##########################################

USAEURdiff = USArate - EURrate
print(USAEURdiff)

USAGBPdiff = USArate - GBPrate
print(USAGBPdiff)

USAJPYdiff = USArate - JPYrate
print(USAJPYdiff)


##############################################################################
############################### EUR ##########################################

EURUSAdiff = EURrate - USArate
print(EURUSAdiff)

EURGBPdiff = EURrate - GBPrate
print(EURGBPdiff)

EURJPYdiff = EURrate - JPYrate
print(EURJPYdiff)


##############################################################################
############################### GBP ##########################################

GBPUSAdiff = GBPrate - USArate
print(GBPUSAdiff)

GBPEURdiff = GBPrate - EURrate
print(GBPEURdiff)

GBPJPYdiff = GBPrate - JPYrate
print(GBPJPYdiff)


##############################################################################
############################### JPY ##########################################

JPYUSAdiff = JPYrate - USArate
print(JPYUSAdiff)

JPYEURdiff = JPYrate - EURrate
print(JPYEURdiff)

JPYGBPdiff = JPYrate - GBPrate
print(JPYGBPdiff)


##############################################################################
########################## BATCH UPDATE (1 API CALL) #########################

# Construct a single list mapping all cells to their respective payload
# Col 2 -> B, Col 3 -> C, Col 4 -> D, Col 5 -> E
updates = [
    # USA/EUR, USA/GBP, USA/JPY
    {'range': 'B180', 'values': [[USAEURdiff]]},
    {'range': 'B181', 'values': [[USAGBPdiff]]},
    {'range': 'B182', 'values': [[USAJPYdiff]]},
    
    # EUR/USA, EUR/GBP, EUR/JPY
    {'range': 'C179', 'values': [[EURUSAdiff]]},
    {'range': 'C181', 'values': [[EURGBPdiff]]},
    {'range': 'C182', 'values': [[EURJPYdiff]]},
    
    # GBP/USA, GBP/EUR, GBP/JPY
    {'range': 'D179', 'values': [[GBPUSAdiff]]},
    {'range': 'D180', 'values': [[GBPEURdiff]]},
    {'range': 'D182', 'values': [[GBPJPYdiff]]},
    
    # JPY/USA, JPY/EUR, JPY/GBP
    {'range': 'E179', 'values': [[JPYUSAdiff]]},
    {'range': 'E180', 'values': [[JPYEURdiff]]},
    {'range': 'E181', 'values': [[JPYGBPdiff]]}
]

# Process update with Retry/Wait safeguard mechanism
retry_api_call(wb.batch_update, updates)
