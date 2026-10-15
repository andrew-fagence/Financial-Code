import os
import json
import time
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# --- CREDENTIALS & SETUP ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets"
]

# Get credentials from GitHub secret environment variable or fallback to local JSON file
if "GCP_CREDENTIALS" in os.environ:
    creds_dict = json.loads(os.environ["GCP_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
else:
    creds = Credentials.from_service_account_file("forexdailybias-5ce3a8ede6c9.json", scopes=scopes)

client = gspread.authorize(creds)

# ID of google sheet workbook
sheet_id = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
sheet = client.open_by_key(sheet_id)
wb = sheet.sheet1  # Defines 'wb' so your subsequent code blocks work

# get and print row headings for testing
values_list = wb.row_values(1)
print(values_list)

# Read all sheet values in one API call to prevent exceeding the read quota
all_values = wb.get_all_values()

def get_cell_value(row, col):
    try:
        return all_values[row - 1][col - 1]
    except IndexError:
        return ''

# We will collect all cell updates in this list and batch upload them in 1 go
updates = []


####################################### USING FED FUNDS RATE #########################################

# Get upper limit USA federal reserve interest rate
def get_us_interest_rate():
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARU"
    df = pd.read_csv(url)
    df["DFEDTARU"] = pd.to_numeric(df["DFEDTARU"], errors="coerce")
    return float(df["DFEDTARU"].dropna().iloc[-1])

rate = get_us_interest_rate()
print(f"US Fed upper interest rate: {rate:.2f}%")

# Get USA Inflation Rate
currentPCEHinflation = float(get_cell_value(12, 31))
currentPCEHinflation = round(currentPCEHinflation, 1)
print(currentPCEHinflation)

# Calculate real interest rate
realInterestRate = rate - currentPCEHinflation
realInterestRate = round(realInterestRate, 2)
print(f"Real interest rate: {realInterestRate}%")

# Queue write to google sheet
updates.append({'range': gspread.utils.rowcol_to_a1(171, 2), 'values': [[realInterestRate]]})


###################################### 1 YEAR REAL INTEREST RATE ###################################
def get_us_real_interest_rate():
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=REAINTRATREARAT1YE"
    df = pd.read_csv(url)
    df["REAINTRATREARAT1YE"] = pd.to_numeric(
        df["REAINTRATREARAT1YE"], errors="coerce"
    )
    return round(df["REAINTRATREARAT1YE"].dropna().iloc[-1], 2)

currentUSRealInterestRate = get_us_real_interest_rate()
print(f"US 1-year real interest rate: {currentUSRealInterestRate:.2f}%")

updates.append({'range': gspread.utils.rowcol_to_a1(172, 2), 'values': [[currentUSRealInterestRate]]})


###################################### 10 YEAR REAL INTEREST RATE ###################################
def get_us_ten_real_interest_rate():
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=REAINTRATREARAT10Y"
    df = pd.read_csv(url)
    df["REAINTRATREARAT10Y"] = pd.to_numeric(
        df["REAINTRATREARAT10Y"], errors="coerce"
    )
    return round(df["REAINTRATREARAT10Y"].dropna().iloc[-1], 2)

currentUSTenRealInterestRate = get_us_ten_real_interest_rate()
print(f"US 10-year real interest rate: {currentUSTenRealInterestRate:.2f}%")

updates.append({'range': gspread.utils.rowcol_to_a1(173, 2), 'values': [[currentUSTenRealInterestRate]]})


########################################### 30 Year Real Interest Rate ##############################
currentThirtyYearYield = float(get_cell_value(146, 11))
print(currentThirtyYearYield)

currentUSThirtyRealInterestRate = currentThirtyYearYield - currentPCEHinflation
currentUSThirtyRealInterestRate = round(currentUSThirtyRealInterestRate, 2)
print(currentUSThirtyRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(174, 2), 'values': [[currentUSThirtyRealInterestRate]]})


####################################### Current EUR inflation rate ##############################################
currentEURInflationRate = float(get_cell_value(13, 13))
print(currentEURInflationRate)


########################################### USING EUR FUNDS RATE ################################################
currentInterestRate = float(get_cell_value(36, 8))
print(currentInterestRate)
currentInterestRealInterestRate = currentInterestRate - currentEURInflationRate
currentInterestRealInterestRate = round(currentInterestRealInterestRate, 2)
print(currentInterestRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(171, 3), 'values': [[currentInterestRealInterestRate]]})


######################################## EUR 1 Year Real Interest Rate ##########################################
print('#############One Year###########')
currentOneYearInterestRate = float(get_cell_value(147, 4))
print(currentOneYearInterestRate)

OneYearRealInterestRate = currentOneYearInterestRate - currentEURInflationRate
OneYearRealInterestRate = round(OneYearRealInterestRate, 2)
print(OneYearRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(172, 3), 'values': [[OneYearRealInterestRate]]})


######################################## EUR 10 Year Real Interest Rate ##########################################
print('############# Ten Year ###########')
currentTenYearInterestRate = float(get_cell_value(147, 9))
print(currentTenYearInterestRate)

TenYearRealInterestRate = currentTenYearInterestRate - currentEURInflationRate
TenYearRealInterestRate = round(TenYearRealInterestRate, 2)
print(TenYearRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(173, 3), 'values': [[TenYearRealInterestRate]]})


######################################## EUR 30 Year Real Interest Rate ##########################################
print('############# Thirty Year ###########')
currentThirtyYearInterestRate = float(get_cell_value(147, 11))
print(currentThirtyYearInterestRate)

ThirtyYearRealInterestRate = currentThirtyYearInterestRate - currentEURInflationRate
ThirtyYearRealInterestRate = round(ThirtyYearRealInterestRate, 2)
print(ThirtyYearRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(174, 3), 'values': [[ThirtyYearRealInterestRate]]})


####################################### Current GBP inflation rate ##############################################
currentGBPInflationRate = float(get_cell_value(14, 13))
print(currentGBPInflationRate)


########################################### USING GBP FUNDS RATE ################################################
currentGBPInterestRate = float(get_cell_value(38, 8))
print(currentGBPInterestRate)
currentGBPInterestRealInterestRate = currentGBPInterestRate - currentGBPInflationRate
currentGBPInterestRealInterestRate = round(currentGBPInterestRealInterestRate, 2)
print(currentGBPInterestRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(171, 4), 'values': [[currentGBPInterestRealInterestRate]]})


######################################## GBP 1 Year Real Interest Rate ##########################################
print('#############One Year###########')
currentGBPOneYearInterestRate = float(get_cell_value(148, 4))
print(currentGBPOneYearInterestRate)

GBPOneYearRealInterestRate = currentGBPOneYearInterestRate - currentGBPInflationRate
GBPOneYearRealInterestRate = round(GBPOneYearRealInterestRate, 2)
print(GBPOneYearRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(172, 4), 'values': [[GBPOneYearRealInterestRate]]})


######################################## GBP 10 Year Real Interest Rate ##########################################
print('############# Ten Year ###########')
currentGBPTenYearInterestRate = float(get_cell_value(148, 9))
print(currentGBPTenYearInterestRate)

GBPTenYearRealInterestRate = currentGBPTenYearInterestRate - currentGBPInflationRate
GBPTenYearRealInterestRate = round(GBPTenYearRealInterestRate, 2)
print(GBPTenYearRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(173, 4), 'values': [[GBPTenYearRealInterestRate]]})


######################################## GBP 30 Year Real Interest Rate ##########################################
print('############# Thirty Year ###########')
currentGBPThirtyYearInterestRate = float(get_cell_value(148, 11))
print(currentGBPThirtyYearInterestRate)

GBPThirtyYearRealInterestRate = currentGBPThirtyYearInterestRate - currentGBPInflationRate
GBPThirtyYearRealInterestRate = round(GBPThirtyYearRealInterestRate, 2)
print(GBPThirtyYearRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(174, 4), 'values': [[GBPThirtyYearRealInterestRate]]})


####################################### Current JPY inflation rate ##############################################
currentJPYInflationRate = float(get_cell_value(15, 13))
print(currentJPYInflationRate)


########################################### USING JPY FUNDS RATE ################################################
currentJPYInterestRate = float(get_cell_value(34, 11))
print(currentJPYInterestRate)
currentJPYInterestRealInterestRate = currentJPYInterestRate - currentJPYInflationRate
currentJPYInterestRealInterestRate = round(currentJPYInterestRealInterestRate, 2)
print(currentJPYInterestRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(171, 5), 'values': [[currentJPYInterestRealInterestRate]]})


######################################## JPY 1 Year Real Interest Rate ##########################################
print('#############One Year###########')
currentJPYOneYearInterestRate = float(get_cell_value(149, 4))
print(currentJPYOneYearInterestRate)

JPYOneYearRealInterestRate = currentJPYOneYearInterestRate - currentJPYInflationRate
JPYOneYearRealInterestRate = round(JPYOneYearRealInterestRate, 2)
print(JPYOneYearRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(172, 5), 'values': [[JPYOneYearRealInterestRate]]})


######################################## JPY 10 Year Real Interest Rate ##########################################
print('############# Ten Year ###########')
currentJPYTenYearInterestRate = float(get_cell_value(149, 9))
print(currentJPYTenYearInterestRate)

JPYTenYearRealInterestRate = currentJPYTenYearInterestRate - currentJPYInflationRate
JPYTenYearRealInterestRate = round(JPYTenYearRealInterestRate, 2)
print(JPYTenYearRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(173, 5), 'values': [[JPYTenYearRealInterestRate]]})


######################################## JPY 30 Year Real Interest Rate ##########################################
print('############# Thirty Year ###########')
currentJPYThirtyYearInterestRate = float(get_cell_value(149, 11))
print(currentJPYThirtyYearInterestRate)

JPYThirtyYearRealInterestRate = currentJPYThirtyYearInterestRate - currentJPYInflationRate
JPYThirtyYearRealInterestRate = round(JPYThirtyYearRealInterestRate, 2)
print(JPYThirtyYearRealInterestRate)

updates.append({'range': gspread.utils.rowcol_to_a1(174, 5), 'values': [[JPYThirtyYearRealInterestRate]]})


# --- BATCH UPLOAD WITH RETRY/WAIT ---
print("\nInitiating batch update to Google Sheets...")
max_retries = 5

for attempt in range(max_retries):
    try:
        wb.batch_update(updates)
        print("Batch update successful!")
        break
    except Exception as e:
        print(f"Error during batch update: {e}")
        if attempt < max_retries - 1:
            print(f"Retrying in 10 seconds... (Attempt {attempt + 1} of {max_retries - 1})")
            time.sleep(10)
        else:
            print("Max retries reached. Batch update failed.")
            raise e
