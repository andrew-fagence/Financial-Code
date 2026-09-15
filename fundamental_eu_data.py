import time
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import fredapi as fa

# ==============================================================================
# 1. SETUP & AUTHENTICATION
# ==============================================================================
scopes = [
    "https://www.googleapis.com/auth/spreadsheets"
]

# Get credentials from JSON file
creds = Credentials.from_service_account_file("forexdailybias-5ce3a8ede6c9.json", scopes=scopes)
client = gspread.authorize(creds)

# ID of google sheet workbook
sheet_id = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
sheet = client.open_by_key(sheet_id)

# Connect specifically to the requested worksheet
wb = sheet.worksheet("Historical Values Storage")

# Get and print row headings for testing
values_list = wb.row_values(1)
print("Row headings:", values_list)

# Setup FRED API
fred = fa.Fred('2d406210f6235b1e9f9e750365bcc8b4')

# Retry wrapper to prevent 429 Rate Limit Errors
def update_cell_with_retry(row, col, value, max_retries=6):
    for attempt in range(max_retries):
        try:
            wb.update_cell(row, col, value)
            return
        except gspread.exceptions.APIError as e:
            if "429" in str(e):
                wait_time = (2 ** attempt) * 5
                print(f"Rate limit 429 hit. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception(f"Failed to update cell after {max_retries} attempts.")


# ==============================================================================
# 2. CORE HICP (EU)
# ==============================================================================
print("\n--- Fetching Core HICP (EU) ---")

URL = "https://data-api.ecb.europa.eu/service/data/HICP/M.U2.N.XEF000.4D0.INX"
params = {"format": "jsondata"}
r = requests.get(URL, params=params)
print("Status:", r.status_code)
r.raise_for_status()
data = r.json()

# Extract series & dates
series = data["dataSets"][0]["series"]
series_key = list(series.keys())[0]
observations = series[series_key]["observations"]
dates = data["structure"]["dimensions"]["observation"][0]["values"]

rows = []
for idx, value in observations.items():
    date = dates[int(idx)]["id"]
    index_value = value[0]
    rows.append((date, index_value))

df = pd.DataFrame(rows, columns=["date", "core_hicp_index"])
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

# Monthly Change
df["monthly_change"] = df["core_hicp_index"].pct_change() * 100
df = df.dropna()
print("\nLatest Core HICP Monthly Data:")
print(df.tail(6))

latest = df.tail(3).reset_index(drop=True)

for i in range(len(latest)):
    date = latest.loc[i, "date"].strftime("%Y-%m-%d")
    value = round(latest.loc[i, "monthly_change"], 4)
    
    update_cell_with_retry(3, 2 + (i * 2), date)
    time.sleep(1)
    update_cell_with_retry(3, 3 + (i * 2), value)
    time.sleep(1)
    print(f"{date} → EU Core HICP MoM: {value}%")

# Quarterly Change
quarterly = df.set_index("date")["core_hicp_index"].resample("QE").last().reset_index()
quarterly["quarterly_change"] = quarterly["core_hicp_index"].pct_change() * 100
quarterly = quarterly.dropna()

print("\nLatest Quarterly Core HICP:")
print(quarterly.tail(6))

latest = quarterly.tail(3).reset_index(drop=True)
for i in range(len(latest)):
    date = latest.loc[i, "date"].strftime("%Y-%m-%d")
    value = round(latest.loc[i, "quarterly_change"], 4)
    
    update_cell_with_retry(8, 2 + (i * 2), date)
    time.sleep(1)
    update_cell_with_retry(8, 3 + (i * 2), value)
    time.sleep(1)
    print(f"{date} → EU Core HICP Quarterly Change: {value}%")

# Yearly Change
URL = "https://data-api.ecb.europa.eu/service/data/HICP/M.U2.N.XEF000.4D0.ANR"
r = requests.get(URL, params=params)
r.raise_for_status()
data = r.json()

series = data["dataSets"][0]["series"]
series_key = list(series.keys())[0]
observations = series[series_key]["observations"]
dates = data["structure"]["dimensions"]["observation"][0]["values"]

rows = []
for idx, value in observations.items():
    date = dates[int(idx)]["id"]
    inflation = value[0]
    rows.append((date, inflation))

df = pd.DataFrame(rows, columns=["date", "core_hicp"])
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

latest = df.tail(3).reset_index(drop=True)
print("\nLatest EU Core HICP Yearly:")
print(latest)

for i in range(len(latest)):
    date = latest.loc[i, "date"].strftime("%Y-%m-%d")
    value = round(latest.loc[i, "core_hicp"], 4)
    
    update_cell_with_retry(13, 2 + (i * 2), date)
    time.sleep(1)
    update_cell_with_retry(13, 3 + (i * 2), value)
    time.sleep(1)
    print(f"{date} → EU Core HICP YoY: {value}%")


# ==============================================================================
# 3. HEADLINE HICP (EU)
# ==============================================================================
print("\n--- Fetching Headline HICP (EU) ---")

URL = "https://data-api.ecb.europa.eu/service/data/HICP/M.U2.N.000000.4D0.INX"
r = requests.get(URL, params=params)
print("Status:", r.status_code)
r.raise_for_status()
data = r.json()

series = data["dataSets"][0]["series"]
series_key = list(series.keys())[0]
observations = series[series_key]["observations"]
dates = data["structure"]["dimensions"]["observation"][0]["values"]

rows = []
for idx, value in observations.items():
    date = dates[int(idx)]["id"]
    index_value = value[0]
    rows.append((date, index_value))

df = pd.DataFrame(rows, columns=["date", "core_hicp_index"])
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

# Monthly
df["monthly_change"] = df["core_hicp_index"].pct_change() * 100
df = df.dropna()

print("\nLatest Headline HICP Monthly Data:")
print(df.tail(6))

latest = df.tail(3).reset_index(drop=True)
for i in range(len(latest)):
    date = latest.loc[i, "date"].strftime("%Y-%m-%d")
    value = round(latest.loc[i, "monthly_change"], 4)
    
    update_cell_with_retry(3, 8 + (i * 2), date)
    time.sleep(1)
    update_cell_with_retry(3, 9 + (i * 2), value)
    time.sleep(1)
    print(f"{date} → EU Headline HICP MoM: {value}%")

# Quarterly
quarterly = df.set_index("date")["core_hicp_index"].resample("QE").last().reset_index()
quarterly["quarterly_change"] = quarterly["core_hicp_index"].pct_change() * 100
quarterly = quarterly.dropna()

print("\nLatest Quarterly Headline HICP:")
print(quarterly.tail(6))

latest = quarterly.tail(3).reset_index(drop=True)
for i in range(len(latest)):
    date = latest.loc[i, "date"].strftime("%Y-%m-%d")
    value = round(latest.loc[i, "quarterly_change"], 4)
    
    update_cell_with_retry(8, 8 + (i * 2), date)
    time.sleep(1)
    update_cell_with_retry(8, 9 + (i * 2), value)
    time.sleep(1)
    print(f"{date} → EU Headline HICP Quarterly Change: {value}%")

# Yearly
URL = "https://data-api.ecb.europa.eu/service/data/HICP/M.U2.N.000000.4D0.ANR"
r = requests.get(URL, params=params)
r.raise_for_status()
data = r.json()

series = data["dataSets"][0]["series"]
series_key = list(series.keys())[0]
observations = series[series_key]["observations"]
dates = data["structure"]["dimensions"]["observation"][0]["values"]

rows = []
for idx, value in observations.items():
    date = dates[int(idx)]["id"]
    inflation = value[0]
    rows.append((date, inflation))

df = pd.DataFrame(rows, columns=["date", "headline_hicp_yoy"])
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

latest = df.tail(3).reset_index(drop=True)
print("\nLatest EU Headline HICP YoY:")
print(latest)

for i in range(len(latest)):
    date = latest.loc[i, "date"].strftime("%Y-%m-%d")
    value = round(latest.loc[i, "headline_hicp_yoy"], 4)
    
    update_cell_with_retry(13, 8 + (i * 2), date)
    time.sleep(1)
    update_cell_with_retry(13, 9 + (i * 2), value)
    time.sleep(1)
    print(f"{date} → EU Headline HICP YoY: {value}%")


# ==============================================================================
# 4. PPI (DOMESTIC)
# ==============================================================================
print("\n--- Fetching PPI Domestic ---")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_inppd_m"

def get_ppi(unit):
    params = {
        "geo": "EA21",
        "indic_bt": "PRC_PRR_DOM",
        "nace_r2": "B-E36",
        "s_adj": "NSA",
        "unit": unit
    }
    r = requests.get(URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    values = data["value"]
    time_index = data["dimension"]["time"]["category"]["index"]
    time_lookup = {v: k for k, v in time_index.items()}
    
    rows = []
    for idx, value in values.items():
        rows.append([time_lookup[int(idx)], float(value)])
        
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

ppi_monthly = get_ppi("PCH_PRE")
print("\nMONTHLY PPI CHANGE")
print(ppi_monthly.tail(6))

ppi_yoy = get_ppi("PCH_SM")
print("\nYEARLY PPI CHANGE")
print(ppi_yoy.tail(6))

ppi_index = get_ppi("I21")
quarterly = ppi_index.set_index("date")["value"].resample("QE").last().reset_index()
quarterly["value"] = quarterly["value"].pct_change() * 100
quarterly = quarterly.rename(columns={"value": "quarterly_change"})

print("\nQUARTERLY PPI CHANGE")
print(quarterly.tail(6))

# Write to Sheets
latest = ppi_monthly.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(3, 14 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(3, 15 + i*2, round(row["value"], 4))
    time.sleep(1)

latest = quarterly.dropna().tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(8, 14 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(8, 15 + i*2, round(row["quarterly_change"], 4))
    time.sleep(1)

latest = ppi_yoy.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(13, 14 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(13, 15 + i*2, round(row["value"], 4))
    time.sleep(1)

print("Google Sheet updated successfully")


# ==============================================================================
# 5. PPI (CORE / EX-ENERGY)
# ==============================================================================
print("\n--- Fetching PPI (Ex-Energy) ---")

def get_ppi_core(unit):
    params = {
        "geo": "EA21",
        "indic_bt": "PRC_PRR_DOM",
        "nace_r2": "B_C_X_MIG_NRG",
        "s_adj": "NSA",
        "unit": unit
    }
    r = requests.get(URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    values = data["value"]
    time_index = data["dimension"]["time"]["category"]["index"]
    time_lookup = {v: k for k, v in time_index.items()}
    
    rows = []
    for idx, value in values.items():
        rows.append([time_lookup[int(idx)], float(value)])
        
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

ppi_monthly = get_ppi_core("PCH_PRE")
print("\nMONTHLY CHANGE")
print(ppi_monthly.tail(6))

ppi_yoy = get_ppi_core("PCH_SM")
print("\nYEARLY CHANGE")
print(ppi_yoy.tail(6))

ppi_index = get_ppi_core("I21")
quarterly = ppi_index.set_index("date")["value"].resample("QE").last().reset_index()
quarterly["value"] = quarterly["value"].pct_change() * 100
quarterly = quarterly.rename(columns={"value": "quarterly_change"})

print("\nQUARTERLY CHANGE")
print(quarterly.tail(6))

# Write to Sheets
latest = ppi_monthly.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(3, 20 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(3, 21 + i*2, round(row["value"], 4))
    time.sleep(1)

latest = quarterly.dropna().tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(8, 20 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(8, 21 + i*2, round(row["quarterly_change"], 4))
    time.sleep(1)

latest = ppi_yoy.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(13, 20 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(13, 21 + i*2, round(row["value"], 4))
    time.sleep(1)

print("Google Sheet updated successfully")


# ==============================================================================
# 6. REAL GDP
# ==============================================================================
print("\n--- Fetching Real GDP ---")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/namq_10_gdp"
params = {
    "format": "JSON",
    "geo": "EA20",
    "na_item": "B1GQ",
    "unit": "CLV10_MEUR",
    "s_adj": "SCA"
}
r = requests.get(URL, params=params)
print("Status:", r.status_code)
r.raise_for_status()
data = r.json()

values = data["value"]
time_index = data["dimension"]["time"]["category"]["index"]
dates = list(time_index.keys())

rows = []
for idx, value in values.items():
    date = dates[int(idx)]
    rows.append((date, value))

gdp = pd.DataFrame(rows, columns=["date", "gdp_level"])
gdp["date"] = pd.to_datetime(gdp["date"], errors="coerce")
gdp = gdp.sort_values("date").reset_index(drop=True)
gdp["date"] = gdp["date"] + pd.offsets.QuarterEnd(0)

# QoQ
gdp["qoq"] = gdp["gdp_level"].pct_change() * 100
gdp = gdp.dropna()

print("\nLatest Euro Area GDP q/q:")
print(gdp.tail(6))

latest = gdp.tail(3).reset_index(drop=True)
for i in range(len(latest)):
    date = latest.loc[i, "date"].strftime("%Y-%m-%d")
    value = round(latest.loc[i, "qoq"], 4)
    
    update_cell_with_retry(26, 2 + (i * 2), date)
    time.sleep(1)
    update_cell_with_retry(26, 3 + (i * 2), value)
    time.sleep(1)
    print(f"{date} → Euro Area GDP q/q: {value}%")

# YoY
gdp["yoy"] = gdp["gdp_level"].pct_change(4) * 100
latest = gdp.dropna().tail(3).reset_index(drop=True)

print("\nLatest Euro Area GDP y/y:")
print(latest)

for i in range(len(latest)):
    date = latest.loc[i, "date"].strftime("%Y-%m-%d")
    value = round(latest.loc[i, "yoy"], 4)
    
    update_cell_with_retry(31, 2 + (i * 2), date)
    time.sleep(1)
    update_cell_with_retry(31, 3 + (i * 2), value)
    time.sleep(1)
    print(f"{date} → Euro Area GDP y/y: {value}%")


# ==============================================================================
# 7. RETAIL SALES
# ==============================================================================
print("\n--- Fetching Retail Sales ---")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_trtu_m"

def get_retail(unit, adjustment):
    params = {
        "freq": "M",
        "geo": "EA20",
        "indic_bt": "VOL_SLS",
        "nace_r2": "G47",
        "s_adj": adjustment,
        "unit": unit
    }
    r = requests.get(URL, params=params, timeout=30)
    print(r.url)
    r.raise_for_status()
    data = r.json()
    values = data["value"]
    time_index = data["dimension"]["time"]["category"]["index"]
    time_lookup = {v: k for k, v in time_index.items()}
    
    rows = []
    for idx, value in values.items():
        rows.append([time_lookup[int(idx)], float(value)])
        
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

monthly = get_retail("PCH_PRE", "SCA")
print("\nMONTHLY RETAIL SALES m/m")
print(monthly.tail(6))

yearly = get_retail("PCH_SM", "CA")
print("\nYEARLY RETAIL SALES y/y")
print(yearly.tail(6))

quarterly = monthly.copy()
quarterly["growth_factor"] = 1 + quarterly["value"] / 100
quarterly = quarterly.set_index("date")["growth_factor"].resample("QE").prod().sub(1).mul(100).reset_index()
quarterly = quarterly.rename(columns={"growth_factor": "qoq"})

print("\nQUARTERLY RETAIL SALES q/q")
print(quarterly.tail(6))

# Write to Sheets
latest = monthly.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(21, 8+i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(21, 9+i*2, round(row["value"], 4))
    time.sleep(1)

latest = quarterly.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(26, 8+i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(26, 9+i*2, round(row["qoq"], 4))
    time.sleep(1)

latest = yearly.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(31, 8+i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(31, 9+i*2, round(row["value"], 4))
    time.sleep(1)

print("Google Sheet updated successfully")


# ==============================================================================
# 8. SERVICES
# ==============================================================================
print("\n--- Fetching Services Data ---")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_setu_m"
params = {
    "freq": "M",
    "geo": "EA20",
    "indic_bt": "NETTUR",
    "nace_r2": "G-N_X_K",
    "s_adj": "SCA",
    "unit": "PCH_PRE"
}
r = requests.get(URL, params=params, timeout=60)
print(r.url)
print("Status:", r.status_code)

data = r.json()
values = data["value"]
time_index = data["dimension"]["time"]["category"]["index"]
time_lookup = {v: k for k, v in time_index.items()}

rows = []
for idx, value in values.items():
    rows.append([time_lookup[int(idx)], float(value)])

services = pd.DataFrame(rows, columns=["date", "mom"])
services["date"] = pd.to_datetime(services["date"])
services = services.sort_values("date").reset_index(drop=True)
latest = services.tail(3).reset_index(drop=True)

print("\nEURO AREA SERVICES MONTHLY CHANGE")
print(latest)

for i, row in latest.iterrows():
    update_cell_with_retry(21, 14 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(21, 15 + i*2, round(row["mom"], 4))
    time.sleep(1)
    print(f"{row['date'].strftime('%Y-%m-%d')} → Services m/m: {round(row['mom'],4)}%")

print("Google Sheet updated successfully")


# ==============================================================================
# 9. INDUSTRIAL PRODUCTION
# ==============================================================================
print("\n--- Fetching Industrial Production ---")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_inpr_m"

def get_industrial_production():
    params = {
        "freq": "M",
        "geo": "EA20",
        "nace_r2": "B-D",
        "s_adj": "SCA",
        "unit": "PCH_PRE"
    }
    r = requests.get(URL, params=params, timeout=30)
    print(r.url)
    r.raise_for_status()
    data = r.json()
    values = data["value"]
    time_index = data["dimension"]["time"]["category"]["index"]
    time_lookup = {v: k for k, v in time_index.items()}
    
    rows = []
    for idx, value in values.items():
        rows.append([time_lookup[int(idx)], float(value)])
        
    df = pd.DataFrame(rows, columns=["date", "mom"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

industrial = get_industrial_production()

print("\nEURO AREA INDUSTRIAL PRODUCTION m/m")
print(industrial.tail(6))

latest = industrial.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(21, 20 + i * 2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(21, 21 + i * 2, round(row["mom"], 4))
    time.sleep(1)
    print(f"{row['date'].strftime('%Y-%m-%d')} → Industrial Production m/m: {row['mom']:.4f}%")

print("Google Sheet updated successfully")


# ==============================================================================
# 10. INDUSTRIAL (PRD) DATA
# ==============================================================================
print("\n--- Fetching Industrial (PRD) ---")

def get_industrial():
    params = {
        "freq": "M",
        "geo": "EA20",
        "indic_bt": "PRD",
        "nace_r2": "B-D",
        "s_adj": "SCA",
        "unit": "PCH_PRE"
    }
    r = requests.get(URL, params=params, timeout=60)
    print(r.url)
    r.raise_for_status()
    data = r.json()
    values = data["value"]
    time_index = data["dimension"]["time"]["category"]["index"]
    lookup = {v: k for k, v in time_index.items()}
    
    rows = []
    for idx, value in values.items():
        rows.append([lookup[int(idx)], float(value)])
        
    df = pd.DataFrame(rows, columns=["date", "mom"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

monthly = get_industrial()
print("\nEURO AREA INDUSTRIAL PRODUCTION m/m")
print(monthly.tail(6))

quarterly = monthly.copy()
quarterly["growth_factor"] = 1 + quarterly["mom"] / 100
quarterly = quarterly.set_index("date")["growth_factor"].resample("QE").prod().sub(1).mul(100).dropna().reset_index()
quarterly = quarterly.rename(columns={"growth_factor": "qoq"})

print("\nEURO AREA INDUSTRIAL PRODUCTION q/q")
print(quarterly.tail(6))

yearly = monthly.copy()
yearly["growth_factor"] = 1 + yearly["mom"] / 100
yearly = yearly.set_index("date")["growth_factor"].rolling(12).apply(lambda x: x.prod()-1).mul(100).dropna().reset_index()
yearly = yearly.rename(columns={"growth_factor": "yoy"})

print("\nEURO AREA INDUSTRIAL PRODUCTION y/y")
print(yearly.tail(6))

# Monthly
for i, row in monthly.tail(3).reset_index(drop=True).iterrows():
    update_cell_with_retry(21, 26 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(21, 27 + i*2, round(row["mom"], 4))
    time.sleep(1)

# Quarterly
for i, row in quarterly.tail(3).reset_index(drop=True).iterrows():
    update_cell_with_retry(26, 26 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(26, 27 + i*2, round(row["qoq"], 4))
    time.sleep(1)

# Yearly
for i, row in yearly.tail(3).reset_index(drop=True).iterrows():
    update_cell_with_retry(31, 26 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(31, 27 + i*2, round(row["yoy"], 4))
    time.sleep(1)


# ==============================================================================
# 11. INDUSTRIAL (PRD) DATA PART 2
# ==============================================================================
# Note: Re-executing identical fetching logic to update distinct cells block
monthly = get_industrial()

quarterly = monthly.copy()
quarterly["factor"] = 1 + quarterly["mom"] / 100
quarterly = quarterly.set_index("date")["factor"].resample("QE").prod().sub(1).mul(100).reset_index()
quarterly = quarterly.rename(columns={"factor": "qoq"})

yearly = monthly.copy()
yearly["factor"] = 1 + yearly["mom"] / 100
yearly = yearly.set_index("date")["factor"].rolling(12).apply(lambda x: x.prod()).sub(1).mul(100).reset_index()
yearly = yearly.rename(columns={"factor": "yoy"})

# Monthly row 21
latest = monthly.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(21, 32 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(21, 33 + i*2, round(row["mom"], 4))
    time.sleep(1)

# Quarterly row 26
latest = quarterly.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(26, 32 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(26, 33 + i*2, round(row["qoq"], 4))
    time.sleep(1)

# Yearly row 31
latest = yearly.dropna().tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(31, 32 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(31, 33 + i*2, round(row["yoy"], 4))
    time.sleep(1)

print("Google Sheet updated successfully")


# ==============================================================================
# 12. EMPLOYMENT
# ==============================================================================
print("\n--- Fetching Employment Data ---")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/namq_10_pe"

def get_employment(unit):
    params = {
        "freq": "Q",
        "geo": "EA20",
        "na_item": "EMP_DC",
        "s_adj": "SCA",
        "unit": unit
    }
    r = requests.get(URL, params=params, timeout=60)
    print(r.url)
    r.raise_for_status()
    data = r.json()
    values = data["value"]
    time_index = data["dimension"]["time"]["category"]["index"]
    lookup = {v: k for k, v in time_index.items()}
    
    rows = []
    for idx, value in values.items():
        rows.append([lookup[int(idx)], float(value)])
        
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(
        df["date"].astype(str)
        .str.replace("Q1", "-03-31")
        .str.replace("Q2", "-06-30")
        .str.replace("Q3", "-09-30")
        .str.replace("Q4", "-12-31")
    )
    return df.sort_values("date").reset_index(drop=True)

quarterly = get_employment("PCH_PRE_PER")
quarterly = quarterly.rename(columns={"value": "qoq"})
print("\nEURO AREA EMPLOYMENT q/q")
print(quarterly.tail(6))

yearly = get_employment("PCH_SM_PER")
yearly = yearly.rename(columns={"value": "yoy"})
print("\nEURO AREA EMPLOYMENT y/y")
print(yearly.tail(6))

# Write to Sheets
latest = quarterly.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(120, 2 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(120, 3 + i*2, round(row["qoq"], 4))
    time.sleep(1)
    print(f"{row['date'].strftime('%Y-%m-%d')} → Employment q/q: {round(row['qoq'],4)}%")

latest = yearly.tail(3).reset_index(drop=True)
for i, row in latest.iterrows():
    update_cell_with_retry(125, 2 + i*2, row["date"].strftime("%Y-%m-%d"))
    time.sleep(1)
    update_cell_with_retry(125, 3 + i*2, round(row["yoy"], 4))
    time.sleep(1)
    print(f"{row['date'].strftime('%Y-%m-%d')} → Employment y/y: {round(row['yoy'],4)}%")

print("Google Sheet updated successfully")


# ==============================================================================
# 13. UNEMPLOYMENT
# ==============================================================================
print("\n--- Fetching Unemployment Data ---")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m"

def get_unemployment():
    params = {
        "freq": "M",
        "geo": "EA21",
        "s_adj": "SA",
        "sex": "T",
        "age": "TOTAL",
        "unit": "PC_ACT"
    }
    r = requests.get(URL, params=params, timeout=60)
    print(r.url)
    r.raise_for_status()
    data = r.json()
    values = data["value"]
    time_index = data["dimension"]["time"]["category"]["index"]
    lookup = {v: k for k, v in time_index.items()}
    
    rows = []
    for idx, value in values.items():
        rows.append([lookup[int(idx)], float(value)])
        
    df = pd.DataFrame(rows, columns=["date", "unemployment_rate"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

monthly = get_unemployment()
print("\nEURO AREA UNEMPLOYMENT RATE MONTHLY")
print(monthly.tail(6))

quarterly = monthly.set_index("date")["unemployment_rate"].resample("QE").mean().reset_index()
print("\nEURO AREA UNEMPLOYMENT RATE QUARTERLY")
print(quarterly.tail(6))

yearly = monthly.copy()
yearly["yoy_change"] = yearly["unemployment_rate"] - yearly["unemployment_rate"].shift(12)
yearly = yearly.dropna()[["date", "yoy_change"]]
print("\nEURO AREA UNEMPLOYMENT RATE YoY CHANGE")
print(yearly.tail(6))

def write_rate_sheet(dataset, row):
    latest = dataset.tail(3).reset_index(drop=True)
    for i, r in latest.iterrows():
        update_cell_with_retry(row, 8 + i*2, r["date"].strftime("%Y-%m-%d"))
        time.sleep(1)
        update_cell_with_retry(row, 9 + i*2, round(r["unemployment_rate"], 2))
        time.sleep(1)
        print(f"{r['date'].strftime('%Y-%m-%d')} → Unemployment rate: {round(r['unemployment_rate'],2)}%")

def write_yoy_sheet(dataset, row):
    latest = dataset.tail(3).reset_index(drop=True)
    for i, r in latest.iterrows():
        update_cell_with_retry(row, 8 + i*2, r["date"].strftime("%Y-%m-%d"))
        time.sleep(1)
        update_cell_with_retry(row, 9 + i*2, round(r["yoy_change"], 2))
        time.sleep(1)
        print(f"{r['date'].strftime('%Y-%m-%d')} → Unemployment YoY change: {round(r['yoy_change'],2)}pp")

write_rate_sheet(monthly, 115)
write_rate_sheet(quarterly, 120)
write_yoy_sheet(yearly, 125)

print("Google Sheet updated successfully")


# ==============================================================================
# 14. LABOUR FORCE PARTICIPATION
# ==============================================================================
print("\n--- Fetching Labour Force Participation ---")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/lfsq_argan"

def get_participation():
    params = {
        "freq": "Q",
        "geo": "EA21",
        "sex": "T",
        "age": "Y15-64",
        "citizen": "TOTAL",
        "unit": "PC"
    }
    r = requests.get(URL, params=params, timeout=60)
    print(r.url)
    r.raise_for_status()
    data = r.json()
    values = data.get("value", {})
    time_index = data["dimension"]["time"]["category"]["index"]
    lookup = {v: k for k, v in time_index.items()}
    
    rows = []
    for idx, value in values.items():
        rows.append([lookup[int(idx)], float(value)])
        
    df = pd.DataFrame(rows, columns=["date", "participation_rate"])
    if df.empty:
        return df
        
    df["date"] = (
        df["date"]
        .str.replace("Q1", "-03-31")
        .str.replace("Q2", "-06-30")
        .str.replace("Q3", "-09-30")
        .str.replace("Q4", "-12-31")
    )
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

quarterly = get_participation()
print("\nEURO AREA LABOUR FORCE PARTICIPATION RATE QUARTERLY")
print(quarterly.tail(6))

yearly = quarterly.set_index("date")["participation_rate"].resample("YE").mean().reset_index()
print("\nEURO AREA LABOUR FORCE PARTICIPATION RATE YEARLY")
print(yearly.tail(6))

def write_sheet(dataset, row):
    latest = dataset.tail(3).reset_index(drop=True)
    for i, r in latest.iterrows():
        update_cell_with_retry(row, 14 + i*2, r["date"].strftime("%Y-%m-%d"))
        time.sleep(1)
        update_cell_with_retry(row, 15 + i*2, round(r["participation_rate"], 2))
        time.sleep(1)
        print(f"{r['date'].strftime('%Y-%m-%d')} → {round(r['participation_rate'],2)}%")

write_sheet(quarterly, 120)
write_sheet(yearly, 125)

print("Google Sheet updated successfully")


# ==============================================================================
# 15. WAGES
# ==============================================================================
print("\n--- Fetching Wages ---")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/lc_lci_r2_q"

def get_wages(unit):
    params = {
        "freq": "Q",
        "geo": "EA21",
        "s_adj": "SCA",
        "nace_r2": "B-S",
        "lcstruct": "D11",
        "unit": unit
    }
    r = requests.get(URL, params=params, timeout=60)
    print(r.url)
    r.raise_for_status()
    data = r.json()
    values = data["value"]
    time_index = data["dimension"]["time"]["category"]["index"]
    lookup = {v: k for k, v in time_index.items()}
    
    rows = []
    for idx, value in values.items():
        rows.append([lookup[int(idx)], float(value)])
        
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(
        df["date"]
        .str.replace("Q1", "-03-31")
        .str.replace("Q2", "-06-30")
        .str.replace("Q3", "-09-30")
        .str.replace("Q4", "-12-31")
    )
    return df.sort_values("date").reset_index(drop=True)

index = get_wages("I20")

quarterly = index.copy()
quarterly["wage_growth"] = quarterly["value"].pct_change() * 100
quarterly = quarterly[["date", "wage_growth"]]
print("\nEURO AREA WAGE GROWTH q/q")
print(quarterly.tail(6))

yearly = index.copy()
yearly["wage_growth"] = yearly["value"].pct_change(4) * 100
yearly = yearly.dropna()[["date", "wage_growth"]]
print("\nEURO AREA WAGE GROWTH y/y")
print(yearly.tail(6))

def write_wage_sheet(df, row):
    latest = df.tail(3).reset_index(drop=True)
    for i, r in latest.iterrows():
        update_cell_with_retry(row, 20 + i*2, r["date"].strftime("%Y-%m-%d"))
        time.sleep(1)
        update_cell_with_retry(row, 21 + i*2, round(r["wage_growth"], 4))
        time.sleep(1)
        print(f"{r['date'].strftime('%Y-%m-%d')} → Wage growth: {round(r['wage_growth'],4)}%")

write_wage_sheet(quarterly, 120)
write_wage_sheet(yearly, 125)

print("Google Sheet updated successfully")


# ==============================================================================
# 16. JOB VACANCY RATE
# ==============================================================================
print("\n--- Fetching Job Vacancy Rate ---")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/jvs_q_nace2"

def get_vacancy_rate():
    params = {
        "freq": "Q",
        "geo": "EA21",
        "s_adj": "SA",
        "nace_r2": "B-S",
        "sizeclas": "TOTAL",
        "indic_em": "JVR"
    }
    r = requests.get(URL, params=params, timeout=60)
    print(r.url)
    r.raise_for_status()
    data = r.json()
    values = data["value"]
    time_index = data["dimension"]["time"]["category"]["index"]
    lookup = {v: k for k, v in time_index.items()}
    
    rows = []
    for idx, value in values.items():
        rows.append([lookup[int(idx)], float(value)])
        
    df = pd.DataFrame(rows, columns=["date", "vacancy_rate"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

quarterly = get_vacancy_rate()
print("\nEURO AREA JOB VACANCY RATE QUARTERLY")
print(quarterly.tail(6))

yearly = quarterly.copy()
yearly["yoy_change"] = yearly["vacancy_rate"] - yearly["vacancy_rate"].shift(4)
yearly = yearly.dropna()[["date", "yoy_change"]]
print("\nEURO AREA JOB VACANCY RATE YoY CHANGE")
print(yearly.tail(6))

def write_vacancy_sheet(dataset, row, value_column):
    latest = dataset.tail(3).reset_index(drop=True)
    for i, r in latest.iterrows():
        update_cell_with_retry(row, 26 + i*2, r["date"].strftime("%Y-%m-%d"))
        time.sleep(1)
        update_cell_with_retry(row, 27 + i*2, round(r[value_column], 4))
        time.sleep(1)
        print(f"{r['date'].strftime('%Y-%m-%d')} → {value_column}: {round(r[value_column],4)}")

write_vacancy_sheet(quarterly, 120, "vacancy_rate")
write_vacancy_sheet(yearly, 125, "yoy_change")

print("Google Sheet fully populated and finished!")
