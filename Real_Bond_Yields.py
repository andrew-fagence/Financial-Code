import os
import json
import time
import gspread
from google.oauth2.service_account import Credentials

def execute_with_retry(func, *args, **kwargs):
    """Executes a function with a retry mechanism for Google API quota errors."""
    max_retries = 5
    base_delay = 5  # seconds
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = base_delay * (2 ** attempt)
                print(f"API error encountered: {e}. Retrying in {sleep_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(sleep_time)
            else:
                raise e

def get_float_cell(wb, row, col):
    """Helper function to fetch and float-cast a cell value with wait/retry."""
    cell = execute_with_retry(wb.cell, row, col)
    return float(cell.value)

scopes = [
    "https://www.googleapis.com/auth/spreadsheets"
]

# Get credentials from GitHub Secret (JSON string)
creds_json = os.environ.get("GCP_CREDENTIALS")
if not creds_json:
    raise ValueError("GCP_CREDENTIALS environment variable is missing.")

creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

# ID of google sheet workbook
sheet_id = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
sheet = execute_with_retry(client.open_by_key, sheet_id)
wb = sheet.sheet1

# get and print row headings for testing
values_list = execute_with_retry(wb.row_values, 1)
print(values_list)

############################# USA #######################################
#Getting current yields
USAOneYRyield = get_float_cell(wb, 146, 4)
USATwoYRyield = get_float_cell(wb, 146, 5)
USAThreeYRyield = get_float_cell(wb, 146, 6)
USAFiveYRyield = get_float_cell(wb, 146, 7)
USASevenYRyield = get_float_cell(wb, 146, 8)
USATenYRyield = get_float_cell(wb, 146, 9)
USATwentyYRyield = get_float_cell(wb, 146, 10)
USAThirtyYRyield = get_float_cell(wb, 146, 11)

# Get USA Inflation Rate
currentPCEHinflation = get_float_cell(wb, 12, 31)
currentPCEHinflation = round(currentPCEHinflation, 2)

# calculate USA yield differential values
USAOneYRyieldDiff = USAOneYRyield - currentPCEHinflation
USATwoYRyieldDiff = USATwoYRyield - currentPCEHinflation
USAThreeYRyieldDiff = USAThreeYRyield - currentPCEHinflation
USAFiveYRyieldDiff = USAFiveYRyield - currentPCEHinflation
USASevenYRyieldDiff = USASevenYRyield - currentPCEHinflation
USATenYRyieldDiff = USATenYRyield - currentPCEHinflation
USATwentyYRyieldDiff = USATwentyYRyield - currentPCEHinflation
USAThirtyYRyieldDiff = USAThirtyYRyield - currentPCEHinflation


######################################################### EUR ########################################################
#Getting current yields
EUROneYRyield = get_float_cell(wb, 147, 4)
EURTwoYRyield = get_float_cell(wb, 147, 5)
EURThreeYRyield = get_float_cell(wb, 147, 6)
EURFiveYRyield = get_float_cell(wb, 147, 7)
EURSevenYRyield = get_float_cell(wb, 147, 8)
EURTenYRyield = get_float_cell(wb, 147, 9)
EURTwentyYRyield = get_float_cell(wb, 147, 10)
EURThirtyYRyield = get_float_cell(wb, 147, 11)

##Current EUR inflation rate ##
currentEURInflationRate = get_float_cell(wb, 13, 13)
print(currentEURInflationRate)

# calculate EUR yield differential values
EUROneYRyieldDiff = EUROneYRyield - currentEURInflationRate
EURTwoYRyieldDiff = EURTwoYRyield - currentEURInflationRate
EURThreeYRyieldDiff = EURThreeYRyield - currentEURInflationRate
EURFiveYRyieldDiff = EURFiveYRyield - currentEURInflationRate
EURSevenYRyieldDiff = EURSevenYRyield - currentEURInflationRate
EURTenYRyieldDiff = EURTenYRyield - currentEURInflationRate
EURTwentyYRyieldDiff = EURTwentyYRyield - currentEURInflationRate
EURThirtyYRyieldDiff = EURThirtyYRyield - currentEURInflationRate


######################################################### GBP ########################################################
#Getting current yields
GBPOneYRyield = get_float_cell(wb, 148, 4)
GBPTwoYRyield = get_float_cell(wb, 148, 5)
GBPThreeYRyield = get_float_cell(wb, 148, 6)
GBPFiveYRyield = get_float_cell(wb, 148, 7)
GBPSevenYRyield = get_float_cell(wb, 148, 8)
GBPTenYRyield = get_float_cell(wb, 148, 9)
GBPTwentyYRyield = get_float_cell(wb, 148, 10)
GBPThirtyYRyield = get_float_cell(wb, 148, 11)

# GBP Inflation Rate
currentGBPInflationRate = get_float_cell(wb, 14, 13)
print(currentGBPInflationRate)

# calculate GBP yield differential values
GBPOneYRyieldDiff = GBPOneYRyield - currentGBPInflationRate
GBPTwoYRyieldDiff = GBPTwoYRyield - currentGBPInflationRate
GBPThreeYRyieldDiff = GBPThreeYRyield - currentGBPInflationRate
GBPFiveYRyieldDiff = GBPFiveYRyield - currentGBPInflationRate
GBPSevenYRyieldDiff = GBPSevenYRyield - currentGBPInflationRate
GBPTenYRyieldDiff = GBPTenYRyield - currentGBPInflationRate
GBPTwentyYRyieldDiff = GBPTwentyYRyield - currentGBPInflationRate
GBPThirtyYRyieldDiff = GBPThirtyYRyield - currentGBPInflationRate


######################################################### JPY ########################################################
print('JPY')
#Getting current yields
JPYOneYRyield = get_float_cell(wb, 149, 4)
JPYTwoYRyield = get_float_cell(wb, 149, 5)
JPYThreeYRyield = get_float_cell(wb, 149, 6)
JPYFiveYRyield = get_float_cell(wb, 149, 7)
JPYSevenYRyield = get_float_cell(wb, 149, 8)
JPYTenYRyield = get_float_cell(wb, 149, 9)
JPYTwentyYRyield = get_float_cell(wb, 149, 10)
JPYThirtyYRyield = get_float_cell(wb, 149, 11)

# Current JPY inflation rate #
currentJPYInflationRate = get_float_cell(wb, 15, 13)
print(currentJPYInflationRate)

# calculate JPY yield differential values
JPYOneYRyieldDiff = JPYOneYRyield - currentJPYInflationRate
JPYTwoYRyieldDiff = JPYTwoYRyield - currentJPYInflationRate
JPYThreeYRyieldDiff = JPYThreeYRyield - currentJPYInflationRate
JPYFiveYRyieldDiff = JPYFiveYRyield - currentJPYInflationRate
JPYSevenYRyieldDiff = JPYSevenYRyield - currentJPYInflationRate
JPYTenYRyieldDiff = JPYTenYRyield - currentJPYInflationRate
JPYTwentyYRyieldDiff = JPYTwentyYRyield - currentJPYInflationRate
JPYThirtyYRyieldDiff = JPYThirtyYRyield - currentJPYInflationRate


######################################################### BATCH UPDATE ########################################################
# Batch updating cells 16-23 (P to W) across rows 146-149 for USA, EUR, GBP, JPY
batch_data = [
    {
        'range': 'P146:W146',
        'values': [[USAOneYRyieldDiff, USATwoYRyieldDiff, USAThreeYRyieldDiff, USAFiveYRyieldDiff, USASevenYRyieldDiff, USATenYRyieldDiff, USATwentyYRyieldDiff, USAThirtyYRyieldDiff]]
    },
    {
        'range': 'P147:W147',
        'values': [[EUROneYRyieldDiff, EURTwoYRyieldDiff, EURThreeYRyieldDiff, EURFiveYRyieldDiff, EURSevenYRyieldDiff, EURTenYRyieldDiff, EURTwentyYRyieldDiff, EURThirtyYRyieldDiff]]
    },
    {
        'range': 'P148:W148',
        'values': [[GBPOneYRyieldDiff, GBPTwoYRyieldDiff, GBPThreeYRyieldDiff, GBPFiveYRyieldDiff, GBPSevenYRyieldDiff, GBPTenYRyieldDiff, GBPTwentyYRyieldDiff, GBPThirtyYRyieldDiff]]
    },
    {
        'range': 'P149:W149',
        'values': [[JPYOneYRyieldDiff, JPYTwoYRyieldDiff, JPYThreeYRyieldDiff, JPYFiveYRyieldDiff, JPYSevenYRyieldDiff, JPYTenYRyieldDiff, JPYTwentyYRyieldDiff, JPYThirtyYRyieldDiff]]
    }
]

# Write all yield differential values in a single API call (wrapped in our retry function)
execute_with_retry(wb.batch_update, batch_data)
print("Batch update completed successfully.")
