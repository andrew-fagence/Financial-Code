import requests
import pandas as pd
from io import BytesIO, StringIO
import re
import gspread
from google.oauth2.service_account import Credentials
import warnings
import time
import urllib.request
import urllib.parse
import subprocess
import sys
import ssl

# Suppress warnings for cleaner execution output
warnings.filterwarnings('ignore')
ssl._create_default_https_context = ssl._create_unverified_context

print("Starting fundamental_jpn_data.py...")

# Global headers to prevent 403 Forbidden WAF blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

# =============================================================================
# SETUP & AUTHENTICATION
# =============================================================================
scopes = [
    "https://www.googleapis.com/auth/spreadsheets"
]

# Get credentials from JSON file
creds = Credentials.from_service_account_file("forexdailybias-5ce3a8ede6c9.json", scopes=scopes)
client = gspread.authorize(creds)

# ID of google sheet workbook
sheet_id = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
sheet = client.open_by_key(sheet_id)

# Target the specific tab for the data
wb = sheet.worksheet("Historical Values Storage")
print("Successfully connected to 'Historical Values Storage' tab.\n")

# Google Sheets API Rate Limit Helper
def api_retry(func, *args, **kwargs):
    max_attempts = 7
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if "429" in str(e) and attempt < max_attempts - 1:
                sleep_time = 2 ** attempt
                print(f"API rate limit (429) hit. Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                raise e
    raise Exception("Max retries exceeded for Google Sheets API")

# =============================================================================
# JAPAN CORE CPI
# =============================================================================
APP_ID = "b0bc8765e50cb21888f0bfc4aa3189a2aab22ae7"
TABLE_ID = "0004052037"

URL = (
    f"https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    f"?appId={APP_ID}"
    f"&statsDataId={TABLE_ID}"
    f"&cdCat01=0161"
    f"&cdArea=00000"
    f"&cdTab=1"
    f"&lang=E"
)

r = requests.get(URL, headers=HEADERS, timeout=60)
r.raise_for_status()
data = r.json()

rows = []

for x in data["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]["VALUE"]:
    if x["@time"][-2:] != "00":
        rows.append([
            pd.to_datetime(
                x["@time"][:4] + x["@time"][6:8],
                format="%Y%m"
            ),
            float(x["$"])
        ])

df = pd.DataFrame(rows, columns=["date", "core_cpi"])
df = df.drop_duplicates("date").sort_values("date").reset_index(drop=True)

# Monthly Core CPI
df["monthly_change"] = df["core_cpi"].pct_change() * 100
monthly = df.dropna(subset=["monthly_change"]).tail(3).reset_index(drop=True)

print("\nMonthly Japan Core CPI")
print(monthly[["date", "monthly_change"]])

# Quarterly Core CPI
quarterly = (
    df.set_index("date")["core_cpi"]
      .resample("QE")
      .last()
      .pct_change()
      .mul(100)
      .dropna()
      .reset_index()
)
quarterly.columns = ["date", "quarterly_change"]

# Remove current incomplete quarter
if df["date"].max().month not in [3, 6, 9, 12]:
    quarterly = quarterly.iloc[:-1]

quarterly = quarterly.tail(3).reset_index(drop=True)

print("\nQuarterly Japan Core CPI")
print(quarterly)

# Yearly Core CPI
df["yearly_change"] = df["core_cpi"].pct_change(12) * 100
yearly = df.dropna(subset=["yearly_change"]).tail(3).reset_index(drop=True)

print("\nYearly Japan Core CPI")
print(yearly[["date", "yearly_change"]])

# Google Sheets Update - Batched
core_monthly_values = []
for _, x in monthly.iterrows():
    core_monthly_values += [x["date"].strftime("%Y-%m-%d"), round(x["monthly_change"], 2)]

core_quarterly_values = []
for _, x in quarterly.iterrows():
    core_quarterly_values += [x["date"].strftime("%Y-%m-%d"), round(x["quarterly_change"], 2)]

core_yearly_values = []
for _, x in yearly.iterrows():
    core_yearly_values += [x["date"].strftime("%Y-%m-%d"), round(x["yearly_change"], 2)]

api_retry(wb.batch_update, [
    {"range": "B5:G5", "values": [core_monthly_values]},
    {"range": "B10:G10", "values": [core_quarterly_values]},
    {"range": "B15:G15", "values": [core_yearly_values]}
])
print("\nJapan Core CPI updated successfully")


# =============================================================================
# JAPAN HEADLINE CPI
# =============================================================================
URL = (
    f"https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    f"?appId={APP_ID}"
    f"&statsDataId={TABLE_ID}"
    f"&cdCat01=0001"
    f"&cdArea=00000"
    f"&cdTab=1"
    f"&lang=E"
)

r = requests.get(URL, headers=HEADERS, timeout=60)
r.raise_for_status()
data = r.json()

rows = []
for x in data["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]["VALUE"]:
    if x["@time"][-2:] != "00":
        rows.append([
            pd.to_datetime(
                x["@time"][:4] + x["@time"][6:8],
                format="%Y%m"
            ),
            float(x["$"])
        ])

df = pd.DataFrame(rows, columns=["date", "headline_cpi"])
df = df.drop_duplicates("date").sort_values("date").reset_index(drop=True)

# Monthly Headline CPI
df["monthly_change"] = df["headline_cpi"].pct_change() * 100
monthly = df.dropna(subset=["monthly_change"]).tail(3).reset_index(drop=True)

print("\nMonthly Japan Headline CPI")
print(monthly[["date", "monthly_change"]])

# Quarterly Headline CPI
quarterly = (
    df.set_index("date")["headline_cpi"]
      .resample("QE")
      .last()
      .pct_change()
      .mul(100)
      .dropna()
      .reset_index()
)
quarterly.columns = ["date", "quarterly_change"]

if df["date"].max().month not in [3, 6, 9, 12]:
    quarterly = quarterly.iloc[:-1]

quarterly = quarterly.tail(3).reset_index(drop=True)

print("\nQuarterly Japan Headline CPI")
print(quarterly)

# Yearly Headline CPI
df["yearly_change"] = df["headline_cpi"].pct_change(12) * 100
yearly = df.dropna(subset=["yearly_change"]).tail(3).reset_index(drop=True)

print("\nYearly Japan Headline CPI")
print(yearly[["date", "yearly_change"]])

# Google Sheets Update - Batched
head_monthly_values = []
for _, x in monthly.iterrows():
    head_monthly_values += [x["date"].strftime("%Y-%m-%d"), round(x["monthly_change"], 2)]

head_quarterly_values = []
for _, x in quarterly.iterrows():
    head_quarterly_values += [x["date"].strftime("%Y-%m-%d"), round(x["quarterly_change"], 2)]

head_yearly_values = []
for _, x in yearly.iterrows():
    head_yearly_values += [x["date"].strftime("%Y-%m-%d"), round(x["yearly_change"], 2)]

api_retry(wb.batch_update, [
    {"range": "H5:M5", "values": [head_monthly_values]},
    {"range": "H10:M10", "values": [head_quarterly_values]},
    {"range": "H15:M15", "values": [head_yearly_values]}
])
print("\nJapan Headline CPI updated successfully")


# =============================================================================
# JAPAN PPI
# =============================================================================
URL = (
    "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
    "?format=json"
    "&lang=en"
    "&db=PR01"
    "&startDate=202001"
    "&endDate=202612"
    "&code=PRCG20_2200000000"
)

r = requests.get(URL, headers=HEADERS, timeout=60)
r.raise_for_status()

data = r.json()
series = data["RESULTSET"][0]["VALUES"]

df = pd.DataFrame({
    "date": pd.to_datetime(series["SURVEY_DATES"], format="%Y%m"),
    "ppi": pd.to_numeric(series["VALUES"], errors="coerce")
})
df = df.dropna().sort_values("date").reset_index(drop=True)

# Monthly PPI
df["monthly_change"] = df["ppi"].pct_change() * 100
monthly = df.dropna(subset=["monthly_change"]).tail(3).reset_index(drop=True)

print("\nMonthly Japan PPI")
print(monthly[["date", "monthly_change"]])

# Quarterly PPI
q = (
    df.assign(quarter=df["date"].dt.to_period("Q"))
      .groupby("quarter")
      .filter(lambda x: len(x) == 3)
      .groupby("quarter")["ppi"]
      .last()
)

quarterly = q.pct_change().mul(100).dropna().tail(3).reset_index()
quarterly["date"] = quarterly["quarter"].dt.end_time.dt.normalize()
quarterly.columns = ["quarter", "quarterly_change", "date"]
quarterly = quarterly[["date", "quarterly_change"]].reset_index(drop=True)

print("\nQuarterly Japan PPI")
print(quarterly)

# Yearly PPI
df["yearly_change"] = df["ppi"].pct_change(12) * 100
yearly = df.dropna(subset=["yearly_change"]).tail(3).reset_index(drop=True)

print("\nYearly Japan PPI")
print(yearly[["date", "yearly_change"]])

# Google Sheets Update - Batched
ppi_monthly_values = []
for _, x in monthly.iterrows():
    ppi_monthly_values += [x["date"].strftime("%Y-%m-%d"), round(x["monthly_change"], 2)]

ppi_quarterly_values = []
for _, x in quarterly.iterrows():
    ppi_quarterly_values += [x["date"].strftime("%Y-%m-%d"), round(x["quarterly_change"], 4)]

ppi_yearly_values = []
for _, x in yearly.iterrows():
    ppi_yearly_values += [x["date"].strftime("%Y-%m-%d"), round(x["yearly_change"], 2)]

api_retry(wb.batch_update, [
    {"range": "N5:S5", "values": [ppi_monthly_values]},
    {"range": "N10:S10", "values": [ppi_quarterly_values]},
    {"range": "N15:S15", "values": [ppi_yearly_values]}
])
print("\nJapan PPI updated successfully")


# =============================================================================
# JAPAN REAL GDP
# =============================================================================
G = "https://www.esri.cao.go.jp/jp/sna/data/data_list/sokuhou/files/2026/qe262/tables/gaku-jk2621.csv"
Q = "https://www.esri.cao.go.jp/jp/sna/data/data_list/sokuhou/files/2026/qe262/tables/nritu-jk2621.csv"

def read_gdp(url):
    return pd.read_csv(
        BytesIO(requests.get(url, headers=HEADERS, timeout=60).content),
        header=None,
        encoding="cp932"
    ).iloc[7:, [0, 1]]

def parse(df, col):
    year = None
    out = []
    for _, r in df.iterrows():
        p = str(r.iloc[0]).strip()
        m = re.match(r"(?:(\d{4})/\s*)?(\d{1,2})-\s*(\d{1,2})", p)
        if not m:
            continue
        if m.group(1):
            year = int(m.group(1))
        q = (int(m.group(2)) - 1) // 3 + 1
        v = pd.to_numeric(str(r.iloc[1]).replace(",", "").strip(), errors="coerce")
        if pd.notna(v):
            out.append([f"{year}Q{q}", v])
    return pd.DataFrame(out, columns=["quarter", col])

g = parse(read_gdp(G), "gdp")
q = parse(read_gdp(Q), "qoq")

# Last 3 completed quarters
quarterly = q.tail(3).reset_index(drop=True)

# Same quarter previous year
g["yoy"] = g["gdp"].pct_change(4) * 100
yearly = g.dropna(subset=["yoy"]).tail(3).reset_index(drop=True)

print("\nJapan Real GDP QoQ Annualized")
print(quarterly)
print("\nJapan Real GDP YoY")
print(yearly[["quarter", "yoy"]])

# Google Sheets Update - Batched
gdp_quarterly_values = []
for _, x in quarterly.iterrows():
    date = pd.Period(x["quarter"], freq="Q").end_time.strftime("%Y-%m-%d")
    gdp_quarterly_values += [date, round(x["qoq"], 2)]

gdp_yearly_values = []
for _, x in yearly.iterrows():
    date = pd.Period(x["quarter"], freq="Q").end_time.strftime("%Y-%m-%d")
    gdp_yearly_values += [date, round(x["yoy"], 2)]

api_retry(wb.batch_update, [
    {"range": "B28:G28", "values": [gdp_quarterly_values]},
    {"range": "B33:G33", "values": [gdp_yearly_values]}
])
print("\nJapan Real GDP updated successfully")


# =============================================================================
# JAPAN RETAIL SALES (E-Stat API + Dynamic WAF Bypass Fallback)
# =============================================================================
# print("\nFetching Japan Retail Sales...")
# 
# def get_estat_retail():
#     APP_ID = "b0bc8765e50cb21888f0bfc4aa3189a2aab22ae7"
#     target_id = "0003348239" 
#     
#     data_url = f"https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData?appId={APP_ID}&statsDataId={target_id}&lang=J"
#     r = requests.get(data_url, headers=HEADERS, timeout=60)
#     r.raise_for_status()
#     data = r.json()
#     
#     class_objs = data.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {}).get("CLASS_INF", {}).get("CLASS_OBJ", [])
#     if isinstance(class_objs, dict): class_objs = [class_objs]
#     elif not isinstance(class_objs, list): class_objs = []
#         
#     retail_code = None
#     cat_id = None
#     
#     for c in class_objs:
#         if not isinstance(c, dict): continue
#         c_id = c.get("@id")
#         classes = c.get("CLASS", [])
#         if isinstance(classes, dict): classes = [classes]
#         if not isinstance(classes, list): continue
#             
#         for cls in classes:
#             if not isinstance(cls, dict): continue
#             name = str(cls.get("@name", ""))
#             # Broad search for retail sales category
#             if "小売" in name and not any(x in name for x in ["自動車", "機械", "燃料"]):
#                 retail_code = cls.get("@code")
#                 cat_id = c_id
#                 break
#         if retail_code: break
#             
#     if not retail_code:
#         raise Exception("Could not dynamically find '小売業' category code in E-Stat dataset.")
#         
#     values = data.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {}).get("DATA_INF", {}).get("VALUE", [])
#     if not isinstance(values, list):
#         values = [values] if values else []
#         
#     rows = []
#     for v in values:
#         if not isinstance(v, dict): continue
#         if v.get(f"@{cat_id}") == retail_code:
#             t_str = str(v.get("@time", ""))
#             if len(t_str) >= 6:
#                 year = t_str[:4]
#                 month = t_str[4:6]
#                 if month != "00" and month.isdigit() and 1 <= int(month) <= 12:
#                     val = pd.to_numeric(v.get("$"), errors="coerce")
#                     if pd.notna(val):
#                         rows.append([pd.Timestamp(int(year), int(month), 1), val])
#                         
#     df = pd.DataFrame(rows, columns=["date", "retail"]).groupby("date")["retail"].first().reset_index()
#     df = df.sort_values("date").reset_index(drop=True)
#     
#     if len(df) < 12:
#         raise Exception("Not enough data points extracted from E-Stat API.")
#     return df
# 
# def get_meti_excel_fallback():
#     try:
#         from curl_cffi import requests as cffi_requests
#     except ImportError:
#         subprocess.check_call([sys.executable, "-m", "pip", "install", "curl_cffi"])
#         from curl_cffi import requests as cffi_requests
#     try:
#         from bs4 import BeautifulSoup
#     except ImportError:
#         subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4"])
#         from bs4 import BeautifulSoup
# 
#     urls_to_check = [
#         "https://www.meti.go.jp/statistics/tyo/syoudou/result-2.html",
#         "https://www.meti.go.jp/statistics/tyo/syoudou/result-2/index.html",
#         "https://www.meti.go.jp/statistics/tyo/syoudou/result/index.html"
#     ]
#     
#     excel_url = None
#     for url in urls_to_check:
#         try:
#             r = cffi_requests.get(url, impersonate="chrome120", timeout=30)
#             if r.status_code == 200:
#                 soup = BeautifulSoup(r.text, 'html.parser')
#                 for link in soup.find_all('a'):
#                     href = link.get('href', '')
#                     text = link.get_text()
#                     if '.xls' in href and any(x in text or x in href for x in ['業種別', '商業販売', '小売', '時系列', 'h2a']):
#                         excel_url = urllib.parse.urljoin(url, href)
#                         break
#             if excel_url: break
#         except Exception:
#             pass
#             
#     if not excel_url:
#         raise Exception("Could not dynamically find Excel link on any known METI page.")
#         
#     r_excel = cffi_requests.get(excel_url, impersonate="chrome120", headers={"Referer": "https://www.meti.go.jp/"}, timeout=45)
#     if r_excel.status_code == 200 and (r_excel.content.startswith(b'PK') or r_excel.content.startswith(b'\xd0')):
#         return BytesIO(r_excel.content)
#         
#     raise Exception("Failed to download the dynamic METI Excel file via WAF bypass.")
# 
# def load_series(b):
#     b.seek(0)
#     xl = pd.ExcelFile(b)
#     best_df = None
#     best_retail_col = -1
#     best_start_row = -1
#     
#     for sheet in xl.sheet_names:
#         df_temp = pd.read_excel(b, sheet_name=sheet, header=None)
#         
#         # KEY FIX: Handle Excel visually merged cells by forward-filling the "Year" column
#         if len(df_temp.columns) > 0:
#             df_temp[0] = df_temp[0].ffill()
#             
#         retail_col = -1
#         start_row = -1
#         for row_idx in range(min(100, len(df_temp))):
#             row_vals = df_temp.iloc[row_idx].astype(str).tolist()
#             for col_idx, val in enumerate(row_vals):
#                 val_clean = str(val).replace(" ", "").replace("\n", "")
#                 if "小売業" in val_clean or "Retail" in val_clean:
#                     retail_col = col_idx
#                     start_row = row_idx + 1
#                     break
#             if retail_col != -1:
#                 break
#                 
#         if retail_col != -1:
#             best_df = df_temp
#             best_retail_col = retail_col
#             best_start_row = start_row
#             if any(x in sheet for x in ["季調", "季節", "月", "第1表", "第１表"]):
#                 break
#                 
#     if best_df is None or best_retail_col == -1:
#         raise Exception(f"Could not dynamically locate '小売業' column. Sheets available: {xl.sheet_names}")
# 
#     df = best_df
#     rows = []
#     
#     for i in range(best_start_row, len(df)):
#         cols = df.iloc[i, 0:5].values
#         clean_cols = []
#         for x in cols:
#             if pd.isna(x): continue
#             s = str(x).strip()
#             # Remove trailing .0 from years parsed as floats
#             if s.endswith('.0'): s = s[:-2]
#             clean_cols.append(s)
#             
#         row_str = "".join(clean_cols)
#         
#         # Dynamically matches: 2025年1月, 2025/01, 2025.1, or merged strings like 20251
#         m = re.search(r"(19\d{2}|20\d{2})\D{0,4}([01]?[0-9])[月\-\/\.]?", row_str)
#         if not m: continue
#             
#         year = int(m.group(1))
#         month = int(m.group(2))
#         if month < 1 or month > 12: continue
#             
#         date = pd.Timestamp(year, month, 1)
#         val_raw = df.iloc[i, best_retail_col]
#         val_str = str(val_raw).replace(',', '').replace('p', '').replace('r', '').replace(' ', '').replace('△', '-').strip()
#         
#         value = pd.to_numeric(val_str, errors="coerce")
#         if pd.notna(value):
#             rows.append([date, value])
#             
#     res = pd.DataFrame(rows, columns=["date", "retail"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)
#     if len(res) < 12:
#         raise Exception(f"Failed to extract sufficient time series data. Found {len(res)} rows.")
#     return res
# 
# monthly_retail = None
# 
# try:
#     monthly_retail = get_estat_retail()
#     print("Successfully retrieved Retail Sales via E-Stat JSON API.")
# except Exception as e:
#     print(f"E-Stat API method failed: {e}")
#     try:
#         b_excel = get_meti_excel_fallback()
#         monthly_retail = load_series(b_excel)
#         print("Successfully retrieved Retail Sales via METI WAF Bypass fallback.")
#     except Exception as e2:
#         print(f"METI Excel fallback method failed: {e2}")
#         raise Exception("All download attempts for Japan Retail Sales completely failed.")
# 
# monthly_retail["change"] = monthly_retail["retail"].pct_change() * 100
# latest_monthly = monthly_retail.dropna(subset=["change"]).tail(3).reset_index(drop=True)
# 
# print("\nJapan Retail Sales Monthly")
# print(latest_monthly[["date", "change"]])
# 
# # Quarterly
# q_retail = monthly_retail.copy()
# q_retail["quarter"] = q_retail["date"].dt.to_period("Q")
# q_retail = (
#     q_retail.groupby("quarter")
#      .filter(lambda x: len(x) == 3)
#      .groupby("quarter")["retail"]
#      .last()
# )
# 
# quarterly_retail = q_retail.pct_change().mul(100).dropna().tail(3).reset_index(name="change")
# quarterly_retail["date"] = quarterly_retail["quarter"].dt.end_time.dt.normalize()
# 
# print("\nJapan Retail Sales Quarterly")
# print(quarterly_retail[["date", "change"]])
# 
# # Yearly
# monthly_retail["yearly_change"] = monthly_retail["retail"].pct_change(12) * 100
# yearly_retail = monthly_retail.dropna(subset=["yearly_change"]).tail(3).reset_index(drop=True)
# 
# print("\nJapan Retail Sales Yearly")
# print(yearly_retail[["date", "yearly_change"]])
# 
# # Google Sheets Update
# monthly_values = []
# for _, x in latest_monthly.iterrows():
#     monthly_values += [x["date"].strftime("%Y-%m-%d"), round(x["change"], 2)]
# 
# quarterly_values = []
# for _, x in quarterly_retail.iterrows():
#     quarterly_values += [x["date"].strftime("%Y-%m-%d"), round(x["change"], 2)]
# 
# yearly_values = []
# for _, x in yearly_retail.iterrows():
#     yearly_values += [x["date"].strftime("%Y-%m-%d"), round(x["yearly_change"], 2)]
# 
# api_retry(wb.batch_update, [
#     {"range": "H23:M23", "values": [monthly_values]},
#     {"range": "H28:M28", "values": [quarterly_values]},
#     {"range": "H33:M33", "values": [yearly_values]}
# ])
# print("\nJapan Retail Sales updated successfully")


# =============================================================================
# JAPAN INDUSTRIAL SHIPMENTS DATA
# =============================================================================
URL = (
    "https://www.e-stat.go.jp/stat-search/file-download"
    "?statInfId=000040172363&fileKind=0"
)

r = requests.get(URL, headers=HEADERS, timeout=60)
r.raise_for_status()
b_ind = BytesIO(r.content)

raw = pd.read_excel(b_ind, sheet_name="出荷", header=None)

dates = pd.to_datetime(
    raw.iloc[2, 4:].astype(str).str.replace(".0", "", regex=False),
    format="%Y%m",
    errors="coerce"
)
values = pd.to_numeric(raw.iloc[3, 4:], errors="coerce")

df = pd.DataFrame({"date": dates.values, "shipments": values.values})
df = df.dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)

if len(df) < 15:
    raise Exception(f"Too few Japan industrial shipments observations: {len(df)}")

df["monthly_change"] = df["shipments"].pct_change() * 100
monthly = df.dropna(subset=["monthly_change"]).tail(3).reset_index(drop=True)

q = df.copy()
q["quarter"] = q["date"].dt.to_period("Q")
q = (
    q.groupby("quarter")
     .filter(lambda x: len(x) == 3)
     .groupby("quarter")["shipments"]
     .last()
)

quarterly = q.pct_change().mul(100).dropna().tail(3).reset_index(name="quarterly_change")
quarterly["date"] = quarterly["quarter"].dt.end_time.dt.normalize()

df["yearly_change"] = df["shipments"].pct_change(12) * 100
yearly = df.dropna(subset=["yearly_change"]).tail(3).reset_index(drop=True)

monthly_values = []
for _, x in monthly.iterrows():
    monthly_values += [x["date"].strftime("%Y-%m-%d"), round(x["monthly_change"], 2)]

quarterly_values = []
for _, x in quarterly.iterrows():
    quarterly_values += [x["date"].strftime("%Y-%m-%d"), round(x["quarterly_change"], 2)]

yearly_values = []
for _, x in yearly.iterrows():
    yearly_values += [x["date"].strftime("%Y-%m-%d"), round(x["yearly_change"], 2)]

api_retry(wb.batch_update, [
    {"range": "Z23:AE23", "values": [monthly_values]},
    {"range": "Z28:AE28", "values": [quarterly_values]},
    {"range": "Z33:AE33", "values": [yearly_values]}
])
print("\nJapan Industrial Shipments updated successfully")


# =============================================================================
# JAPAN INDUSTRIAL PRODUCTION DATA
# =============================================================================
raw = pd.read_excel(b_ind, sheet_name="生産", header=None)

industry_row = 3
start_col = 4
dates = pd.to_datetime(
    raw.iloc[2, start_col:].astype(str).str.replace(".0", "", regex=False),
    format="%Y%m",
    errors="coerce"
)
values = pd.to_numeric(raw.iloc[industry_row, start_col:], errors="coerce")

df = pd.DataFrame({"date": dates.values, "production": values.values})
df = df.dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)

if len(df) < 15:
    raise Exception(f"Too few Japan industrial production observations: {len(df)}")

df["monthly_change"] = df["production"].pct_change() * 100
monthly = df.dropna(subset=["monthly_change"]).tail(3).reset_index(drop=True)

q = df.copy()
q["quarter"] = q["date"].dt.to_period("Q")
q = (
    q.groupby("quarter")
     .filter(lambda x: len(x) == 3)
     .groupby("quarter")["production"]
     .last()
)

quarterly = q.pct_change().mul(100).dropna().tail(3).reset_index(name="quarterly_change")
quarterly["date"] = quarterly["quarter"].dt.end_time.dt.normalize()

df["yearly_change"] = df["production"].pct_change(12) * 100
yearly = df.dropna(subset=["yearly_change"]).tail(3).reset_index(drop=True)

monthly_values = []
for _, x in monthly.iterrows():
    monthly_values += [x["date"].strftime("%Y-%m-%d"), round(x["monthly_change"], 2)]

quarterly_values = []
for _, x in quarterly.iterrows():
    quarterly_values += [x["date"].strftime("%Y-%m-%d"), round(x["quarterly_change"], 2)]

yearly_values = []
for _, x in yearly.iterrows():
    yearly_values += [x["date"].strftime("%Y-%m-%d"), round(x["yearly_change"], 2)]

api_retry(wb.batch_update, [
    {"range": "AF23:AK23", "values": [monthly_values]},
    {"range": "AF28:AK28", "values": [quarterly_values]},
    {"range": "AF33:AK33", "values": [yearly_values]}
])
print("\nJapan Industrial Production updated successfully")


# =============================================================================
# JAPAN EMPLOYMENT DATA (NFP)
# =============================================================================
URL = (
    "https://www.e-stat.go.jp/stat-search/file-download"
    "?statInfId=000031831358&fileKind=0"
)

r = requests.get(URL, headers=HEADERS, timeout=60)
r.raise_for_status()

raw = pd.read_excel(BytesIO(r.content), sheet_name="季節調整値", header=None)

year_raw = raw.iloc[10:, 0].astype(str).str.strip()
month_raw = raw.iloc[10:, 1].astype(str).str.strip()

year = year_raw.str.extract(r"((?:19|20)\d{2})", expand=False).ffill()
month = month_raw.str.extract(r"(1[0-2]|0?[1-9])", expand=False)
employed = pd.to_numeric(raw.iloc[10:, 7], errors="coerce")

df = pd.DataFrame({
    "year": pd.to_numeric(year, errors="coerce"),
    "month": pd.to_numeric(month, errors="coerce"),
    "employed": employed
})
df = df[df["year"].between(1950, 2030) & df["month"].between(1, 12) & df["employed"].notna()].copy()

df["date"] = pd.to_datetime({
    "year": df["year"].astype(int),
    "month": df["month"].astype(int),
    "day": 1
})
df = df[["date", "employed"]].drop_duplicates("date").sort_values("date").reset_index(drop=True)

if len(df) < 15:
    raise Exception(f"Too few Japan employment observations: {len(df)}")

df["monthly_change"] = df["employed"].diff()
monthly = df.dropna(subset=["monthly_change"]).tail(3).reset_index(drop=True)

q = df.copy()
q["quarter"] = q["date"].dt.to_period("Q")
q = q.groupby("quarter").filter(lambda x: len(x) == 3).groupby("quarter")["employed"].mean()
quarterly = q.diff().dropna().tail(3).reset_index(name="quarterly_change")
quarterly["date"] = quarterly["quarter"].dt.end_time.dt.normalize()

y = df[["date", "employed"]].copy()
y["comparison_date"] = y["date"] - pd.DateOffset(years=1)
y = y.merge(
    df[["date", "employed"]].rename(columns={"date": "comparison_date", "employed": "previous_year_employed"}),
    on="comparison_date",
    how="left"
)
y["yearly_change"] = y["employed"] - y["previous_year_employed"]
yearly = y.dropna(subset=["yearly_change"]).tail(3).reset_index(drop=True)

def make_values(data, col):
    out = []
    for _, x in data.iterrows():
        out += [x["date"].strftime("%Y-%m-%d"), round(float(x[col]), 1)]
    return out

api_retry(wb.batch_update, [
    {"range": "B117:G117", "values": [make_values(monthly, "monthly_change")]},
    {"range": "B122:G122", "values": [make_values(quarterly, "quarterly_change")]},
    {"range": "B127:G127", "values": [make_values(yearly, "yearly_change")]}
])
print("\nJapan NFP updated successfully")


# =============================================================================
# JAPAN UNEMPLOYMENT RATE
# =============================================================================
def number(x):
    if pd.isna(x): return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(x).replace(",", ""))
    return float(m.group()) if m else None

rows = []
current_year = None
for i in range(10, len(raw)):
    y_val = number(raw.iloc[i, 0])
    if y_val is not None and 1950 <= y_val <= 2030:
        current_year = int(y_val)
    if current_year is None:
        continue
    m_val = number(raw.iloc[i, 1])
    if m_val is None or not 1 <= m_val <= 12:
        continue
    rate = number(raw.iloc[i, 19])
    if rate is None:
        continue
    rows.append([pd.Timestamp(current_year, int(m_val), 1), rate])

df = pd.DataFrame(rows, columns=["date", "unemployment_rate"])
df = df.drop_duplicates("date").sort_values("date").reset_index(drop=True)

jan_2026 = pd.Timestamp("2026-01-01")
if jan_2026 not in df["date"].values:
    df.loc[len(df)] = [jan_2026, 2.7]
df = df.sort_values("date").reset_index(drop=True)

monthly = df.tail(3).reset_index(drop=True)

q = df.copy()
q["quarter"] = q["date"].dt.to_period("Q")
q = q.groupby("quarter").filter(lambda x: len(x) == 3)
q = q.groupby("quarter")["unemployment_rate"].mean().reset_index(name="unemployment_rate")
q["previous_quarter"] = q["quarter"].shift(1)
q = q[q["previous_quarter"].notna() & (q["quarter"].astype(int) == q["previous_quarter"].astype(int) + 1)]

quarterly = q.tail(3).reset_index(drop=True)
quarterly["date"] = quarterly["quarter"].dt.end_time.dt.normalize()

y_rate = df.copy()
y_rate["previous_year_rate"] = y_rate["unemployment_rate"].shift(12)
y_rate["yoy_points"] = y_rate["unemployment_rate"] - y_rate["previous_year_rate"]
yearly = y_rate.dropna(subset=["previous_year_rate"]).tail(3).reset_index(drop=True)

monthly_values = []
for _, x in monthly.iterrows():
    monthly_values += [x["date"].strftime("%Y-%m-%d"), round(float(x["unemployment_rate"]), 2)]

quarterly_values = []
for _, x in quarterly.iterrows():
    quarterly_values += [x["date"].strftime("%Y-%m-%d"), round(float(x["unemployment_rate"]), 2)]

yearly_values = []
for _, x in yearly.iterrows():
    yearly_values += [x["date"].strftime("%Y-%m-%d"), round(float(x["unemployment_rate"]), 2)]

api_retry(wb.batch_update, [
    {"range": "H117:M117", "values": [monthly_values]},
    {"range": "H122:M122", "values": [quarterly_values]},
    {"range": "H127:M127", "values": [yearly_values]}
])
print("\nJapan Unemployment Rate updated successfully")


# =============================================================================
# JAPAN LABOUR FORCE PARTICIPATION RATE
# =============================================================================
try:
    import html5lib
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "html5lib"])

URL = "https://ecitizen.jp/statdb/StatsData/0003005865"
html = requests.get(URL, headers=HEADERS, timeout=60).text
tables = pd.read_html(StringIO(html))
t = max(tables, key=lambda x: x.shape[0])
t.columns = [str(c).strip() for c in t.columns]

t = t[
    (t.iloc[:, 0].astype(str) == "率") &
    (t.iloc[:, 1].astype(str) == "全産業") &
    (t.iloc[:, 2].astype(str) == "労働力人口") &
    (t.iloc[:, 3].astype(str) == "総数") &
    (t.iloc[:, 4].astype(str) == "全国")
].copy()

t["date"] = pd.to_datetime(
    t.iloc[:, 5].astype(str).str.replace("年", "-", regex=False).str.replace("月", "", regex=False),
    format="%Y-%m",
    errors="coerce"
)
t["lfpr"] = pd.to_numeric(t.iloc[:, 7], errors="coerce")

df = t[["date", "lfpr"]].dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)

if len(df) < 15:
    raise Exception(f"Too few LFPR observations: {len(df)}")

monthly = df.tail(3).reset_index(drop=True)

q = df.copy()
q["quarter"] = q["date"].dt.to_period("Q")
q = q.groupby("quarter").filter(lambda x: len(x) == 3)
quarterly = q.groupby("quarter")["lfpr"].mean().tail(3).reset_index(name="lfpr")
quarterly["date"] = quarterly["quarter"].dt.end_time.dt.normalize()

y = df.copy()
y["yoy"] = y["lfpr"] - y["lfpr"].shift(12)
yearly = y.dropna(subset=["yoy"]).tail(3)

def vals(d, col):
    out = []
    for _, x in d.iterrows():
        out += [x["date"].strftime("%Y-%m-%d"), round(float(x[col]), 2)]
    return out

api_retry(wb.batch_update, [
    {"range": "N117:S117", "values": [vals(monthly, "lfpr")]},
    {"range": "N122:S122", "values": [vals(quarterly, "lfpr")]},
    {"range": "N127:S127", "values": [vals(yearly, "lfpr")]}
])
print("\nJapan Labour Force Participation Rate updated successfully")


# =============================================================================
# JAPAN AVERAGE HOURLY EARNINGS
# =============================================================================
C = "https://www.jil.go.jp/english/estatis/eshuyo/e0301.html"
HRS = "https://www.jil.go.jp/english/estatis/eshuyo/e0401.html"
months_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

def load(url, word):
    t = next(x for x in pd.read_html(StringIO(requests.get(url, headers=HEADERS, timeout=60).text)) if word in x.to_string())
    rows = []
    year = None
    for _, r in t.iterrows():
        a = [str(x).strip() for x in r]
        y_val = next((int(x) for x in a if re.fullmatch(r"20\d{2}", x)), None)
        if y_val: year = y_val
        m_val = next((months_map[x[:3]] for x in a if x[:3] in months_map), None)
        if not year or not m_val: continue
        i = next(i for i, x in enumerate(a) if x[:3] in months_map)
        nums = [float(z.group().replace(",", "")) for x in a[i+1:] if (z := re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", x.replace("p", "").replace("r", "")))]
        if nums: rows.append([pd.Timestamp(year, m_val, 1), nums[0]])
    return pd.DataFrame(rows, columns=["date", "value"]).drop_duplicates("date")

cash = load(C, "Total cash earnings").rename(columns={"value": "cash"})
hours = load(HRS, "Total hours worked").rename(columns={"value": "hours"})

cash = pd.concat([cash, pd.DataFrame([["2025-04-01", 301698]], columns=["date", "cash"])], ignore_index=True)
hours = pd.concat([hours, pd.DataFrame([["2025-04-01", 139.5]], columns=["date", "hours"])], ignore_index=True)
cash["date"] = pd.to_datetime(cash["date"])
hours["date"] = pd.to_datetime(hours["date"])

df = cash.merge(hours, on="date").sort_values("date").tail(15).reset_index(drop=True)
df["hourly"] = df.cash / df.hours

df["monthly"] = df.hourly.pct_change() * 100
monthly = df.dropna(subset=["monthly"]).tail(3)

q = df.assign(q=df.date.dt.to_period("Q")).groupby("q").filter(lambda x: len(x) == 3).groupby("q").hourly.mean()
quarterly = q.pct_change().mul(100).dropna().tail(3).reset_index(name="quarterly")
quarterly["date"] = quarterly.q.dt.end_time.dt.normalize()

df["yearly"] = df.hourly.pct_change(12) * 100
yearly = df.dropna(subset=["yearly"]).tail(3)

def vals_ahe(d, c):
    return sum(([x.date.strftime("%Y-%m-%d"), round(float(x[c]), 2)] for _, x in d.iterrows()), [])

api_retry(wb.batch_update, [
    {"range": "T117:Y117", "values": [vals_ahe(monthly, "monthly")]},
    {"range": "T122:Y122", "values": [vals_ahe(quarterly, "quarterly")]},
    {"range": "T127:Y127", "values": [vals_ahe(yearly, "yearly")]}
])
print("\nJapan Average Hourly Earnings updated successfully")


# =============================================================================
# JAPAN INITIAL JOBLESS CLAIMS PROXY
# =============================================================================
URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040460962&fileKind=0"
r = requests.get(URL, headers=HEADERS, timeout=60)
r.raise_for_status()
raw = pd.read_excel(BytesIO(r.content), header=None)

years = {}
for c, v in enumerate(raw.iloc[2]):
    s = str(v)
    m = pd.Series([s]).str.extract(r"((?:19|20)\d{2})年度")[0].iloc[0]
    if pd.notna(m): years[c] = int(m)

months_map_claims = {"4月": 4, "5月": 5, "6月": 6, "7月": 7, "8月": 8, "9月": 9, "10月": 10, "11月": 11, "12月": 12, "1月": 1, "2月": 2, "3月": 3}

rows = []
for r_idx in range(4, len(raw)):
    m_val = months_map_claims.get(str(raw.iloc[r_idx, 0]).strip())
    if not m_val: continue
    for c, fy in years.items():
        v = pd.to_numeric(raw.iloc[r_idx, c], errors="coerce")
        if pd.notna(v):
            rows.append([pd.Timestamp(fy if m_val >= 4 else fy + 1, m_val, 1), float(v)])

df = pd.DataFrame(rows, columns=["date", "claims"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)

df["monthly"] = df["claims"].pct_change() * 100
monthly = df.dropna(subset=["monthly"]).tail(3)

q = df.assign(q=df["date"].dt.to_period("Q"))
q = q.groupby("q").filter(lambda x: len(x) == 3).groupby("q")["claims"].mean()
quarterly = q.pct_change().mul(100).dropna().tail(3).reset_index(name="quarterly")
quarterly["date"] = quarterly["q"].dt.end_time.dt.normalize()

df["yearly"] = df["claims"].pct_change(12) * 100
yearly = df.dropna(subset=["yearly"]).tail(3)

def vals_claims(d, c):
    return sum(([x["date"].strftime("%Y-%m-%d"), round(float(x[c]), 2)] for _, x in d.iterrows()), [])

api_retry(wb.batch_update, [
    {"range": "Z117:AE117", "values": [vals_claims(monthly, "monthly")]},
    {"range": "Z122:AE122", "values": [vals_claims(quarterly, "quarterly")]},
    {"range": "Z127:AE127", "values": [vals_claims(yearly, "yearly")]}
])
print("\nJapan Initial Jobless Claims proxy updated successfully")


# =============================================================================
# JAPAN JOB OPENINGS
# =============================================================================
# URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040478164&fileKind=0"
# r = requests.get(URL, headers=HEADERS, timeout=60)
# r.raise_for_status()
# raw = pd.read_excel(BytesIO(r.content), header=None)
# 
# months_list = range(1, 13)
# rows = []
# 
# for i in range(5, len(raw)):
#     y_val = str(raw.iloc[i, 0]).replace("年", "").strip()
#     if not y_val.isdigit(): continue
#     y_val = int(y_val)
#     for m_val in months_list:
#         v = pd.to_numeric(raw.iloc[i, 19 + m_val], errors="coerce")
#         if pd.notna(v):
#             rows.append([pd.Timestamp(y_val, m_val, 1), float(v)])
# 
# df = pd.DataFrame(rows, columns=["date", "openings"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)
# 
# df["monthly"] = df["openings"].pct_change() * 100
# monthly = df.dropna(subset=["monthly"]).tail(3)
# 
# q = df.assign(q=df.date.dt.to_period("Q"))
# q = q.groupby("q").filter(lambda x: len(x) == 3).groupby("q").openings.mean()
# quarterly = q.pct_change().mul(100).dropna().tail(3).reset_index(name="quarterly")
# quarterly["date"] = quarterly.q.dt.end_time.dt.normalize()
# 
# df["yearly"] = df["openings"].pct_change(12) * 100
# yearly = df.dropna(subset=["yearly"]).tail(3)
# 
# def vals_openings(d, c):
#     return sum(([x.date.strftime("%Y-%m-%d"), round(float(x[c]), 2)] for _, x in d.iterrows()), [])
# 
# api_retry(wb.batch_update, [
#     {"range": "AF117:AK117", "values": [vals_openings(monthly, "monthly")]},
#     {"range": "AF122:AK122", "values": [vals_openings(quarterly, "quarterly")]},
#     {"range": "AF127:AK127", "values": [vals_openings(yearly, "yearly")]}
# ])
# 
# print("\nJapan Job Openings updated successfully")
