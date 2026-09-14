import requests
import pandas as pd
import gspread
import re
import fredapi as fa
from google.oauth2.service_account import Credentials
from io import BytesIO, StringIO

# ==============================================================================
# 1. SETUP & AUTHENTICATION
# ==============================================================================

# Google Sheets Authentication
scopes = [
    "https://www.googleapis.com/auth/spreadsheets"
]

# Get credentials from JSON file (ensure this file is available in your deployment environment)
creds = Credentials.from_service_account_file("forexdailybias-5ce3a8ede6c9.json", scopes=scopes)
client = gspread.authorize(creds)

# ID of google sheet workbook
sheet_id = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
sheet = client.open_by_key(sheet_id)

# Connect explicitly to the requested Historical Values Storage sheet
wb = sheet.worksheet("Historical Values Storage")
print("Connected to 'Historical Values Storage' sheet successfully.")

# FRED API Setup
fred = fa.Fred('2d406210f6235b1e9f9e750365bcc8b4')


# ==============================================================================
# 2. UK CORE CPI
# ==============================================================================

print("\nProcessing UK Core CPI...")
SERIES_ID_CORE = "DKI7"
URL_CORE_MOM = f"https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/{SERIES_ID_CORE}/mm23/data"

r = requests.get(URL_CORE_MOM, timeout=30)
r.raise_for_status()
data = r.json()

rows = []
for obs in data["months"]:
    rows.append([pd.to_datetime(obs["date"]), float(obs["value"])])

df_core = pd.DataFrame(rows, columns=["date", "core_cpi_mom"])
df_core = df_core.sort_values("date").reset_index(drop=True)

# Monthly Core CPI
latest_3_core = df_core.tail(3).reset_index(drop=True)
row_m, col_m = 4, 2   # Row 4, Column B
for i, r_val in latest_3_core.iterrows():
    wb.update_cell(row_m, col_m + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(row_m, col_m + (i * 2) + 1, round(r_val["core_cpi_mom"], 2))
print("Last 3 months Core CPI MoM updated successfully")

# Quarterly Core CPI
quarterly_core = (
    df_core.set_index("date")["core_cpi_mom"]
    .resample("QE")
    .apply(lambda x: ((1 + x / 100).prod() - 1) * 100)
    .reset_index()
)
quarterly_core.columns = ["date", "core_cpi_quarterly"]
latest_3_quarters_core = quarterly_core.tail(3).reset_index(drop=True)
row_q, col_q = 9, 2   # Row 9, Column B
for i, r_val in latest_3_quarters_core.iterrows():
    wb.update_cell(row_q, col_q + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(row_q, col_q + (i * 2) + 1, round(r_val["core_cpi_quarterly"], 4))
print("Quarterly Core CPI changes updated successfully")

# Yearly Core CPI
SERIES_ID_CORE_YOY = "DKO8"
URL_CORE_YOY = f"https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/{SERIES_ID_CORE_YOY}/mm23/data"
r = requests.get(URL_CORE_YOY, timeout=30)
r.raise_for_status()
data = r.json()
rows = []
for obs in data["months"]:
    rows.append([pd.to_datetime(obs["date"]), float(obs["value"])])
df_core_yoy = pd.DataFrame(rows, columns=["date", "core_cpi_yoy"])
df_core_yoy = df_core_yoy.sort_values("date").reset_index(drop=True)

latest_3_core_yoy = df_core_yoy.tail(3).reset_index(drop=True)
row_y, col_y = 14, 2   # Row 14, Column B
for i, r_val in latest_3_core_yoy.iterrows():
    wb.update_cell(row_y, col_y + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(row_y, col_y + (i * 2) + 1, round(r_val["core_cpi_yoy"], 2))
print("Last 3 Core CPI YoY observations updated successfully")


# ==============================================================================
# 3. UK HEADLINE CPI
# ==============================================================================

print("\nProcessing UK Headline CPI...")
SERIES_ID_CPI = "D7BT"
URL_CPI = f"https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/{SERIES_ID_CPI}/mm23/data"
r = requests.get(URL_CPI, timeout=30)
r.raise_for_status()
data = r.json()

rows = []
for obs in data["months"]:
    rows.append([pd.to_datetime(obs["date"]), float(obs["value"])])
df_cpi = pd.DataFrame(rows, columns=["date", "cpi_index"])
df_cpi = df_cpi.sort_values("date").reset_index(drop=True)
df_cpi["cpi_mom"] = (df_cpi["cpi_index"] / df_cpi["cpi_index"].shift(1) - 1) * 100

# Monthly Headline CPI
latest_3_cpi = df_cpi.dropna().tail(3).reset_index(drop=True)
row_m, col_m = 4, 8   # Row 4, Column H
for i, r_val in latest_3_cpi.iterrows():
    wb.update_cell(row_m, col_m + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(row_m, col_m + (i * 2) + 1, round(r_val["cpi_mom"], 2))
print("UK Headline CPI monthly updated successfully")

# Quarterly Headline CPI
quarterly_cpi = (
    df_cpi.dropna(subset=["cpi_mom"])
    .set_index("date")["cpi_mom"]
    .resample("QE")
    .apply(lambda x: ((1 + x / 100).prod() - 1) * 100)
    .reset_index()
)
quarterly_cpi.columns = ["date", "cpi_quarterly"]
latest_3_quarters_cpi = quarterly_cpi.tail(3).reset_index(drop=True)
row_q, col_q = 9, 8   # Row 9, Column H
for i, r_val in latest_3_quarters_cpi.iterrows():
    wb.update_cell(row_q, col_q + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(row_q, col_q + (i * 2) + 1, round(r_val["cpi_quarterly"], 4))
print("UK Headline CPI quarterly updated successfully")

# Yearly Headline CPI
SERIES_ID_CPI_YOY = "D7G7"
URL_CPI_YOY = f"https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/{SERIES_ID_CPI_YOY}/mm23/data"
r = requests.get(URL_CPI_YOY, timeout=30)
r.raise_for_status()
data = r.json()
rows = []
for obs in data["months"]:
    rows.append([pd.to_datetime(obs["date"]), float(obs["value"])])
df_cpi_yearly = pd.DataFrame(rows, columns=["date", "cpi_yoy"])
df_cpi_yearly = df_cpi_yearly.sort_values("date").reset_index(drop=True)

latest_3_cpi_yearly = df_cpi_yearly.tail(3).reset_index(drop=True)
row_y, col_y = 14, 8   # Row 14, Column H
for i, r_val in latest_3_cpi_yearly.iterrows():
    wb.update_cell(row_y, col_y + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(row_y, col_y + (i * 2) + 1, round(r_val["cpi_yoy"], 2))
print("UK Headline CPI yearly updated successfully")


# ==============================================================================
# 4. UK HEADLINE PPI
# ==============================================================================

print("\nProcessing UK Headline PPI...")
SERIES_ID_PPI = "GB7S"
URL_PPI = f"https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/{SERIES_ID_PPI}/ppi/data"
r = requests.get(URL_PPI, timeout=30)
r.raise_for_status()
data = r.json()

rows = []
for obs in data["months"]:
    rows.append([pd.to_datetime(obs["date"]), float(obs["value"])])
df_ppi = pd.DataFrame(rows, columns=["date", "ppi_index"])
df_ppi = df_ppi.sort_values("date").reset_index(drop=True)
df_ppi["ppi_mom"] = (df_ppi["ppi_index"] / df_ppi["ppi_index"].shift(1) - 1) * 100

# Monthly PPI
latest_3_ppi = df_ppi.dropna().tail(3).reset_index(drop=True)
row_m, col_m = 4, 14   # Row 4, Column N
for i, r_val in latest_3_ppi.iterrows():
    wb.update_cell(row_m, col_m + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(row_m, col_m + (i * 2) + 1, round(r_val["ppi_mom"], 2))
print("UK Headline PPI monthly updated successfully")

# Quarterly PPI
quarterly_ppi = (
    df_ppi.dropna(subset=["ppi_mom"])
    .set_index("date")["ppi_mom"]
    .resample("QE")
    .apply(lambda x: ((1 + x / 100).prod() - 1) * 100)
    .reset_index()
)
quarterly_ppi.columns = ["date", "ppi_quarterly"]
latest_3_quarters_ppi = quarterly_ppi.tail(3).reset_index(drop=True)
row_q, col_q = 9, 14   # Row 9, Column N
for i, r_val in latest_3_quarters_ppi.iterrows():
    wb.update_cell(row_q, col_q + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(row_q, col_q + (i * 2) + 1, round(r_val["ppi_quarterly"], 4))
print("UK Headline PPI quarterly updated successfully")

# Yearly PPI
df_ppi["ppi_yoy"] = (df_ppi["ppi_index"] / df_ppi["ppi_index"].shift(12) - 1) * 100
latest_3_ppi_yearly = df_ppi.dropna(subset=["ppi_yoy"]).tail(3).reset_index(drop=True)
row_y, col_y = 14, 14   # Row 14, Column N
for i, r_val in latest_3_ppi_yearly.iterrows():
    wb.update_cell(row_y, col_y + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(row_y, col_y + (i * 2) + 1, round(r_val["ppi_yoy"], 2))
print("UK Headline PPI yearly updated successfully")


# ==============================================================================
# 5. UK GDP
# ==============================================================================

print("\nProcessing UK GDP...")
def quarter_to_date(q):
    year = int(q[:4])
    quarter = q[-1]
    if quarter == "1": return pd.Timestamp(year, 3, 31)
    elif quarter == "2": return pd.Timestamp(year, 6, 30)
    elif quarter == "3": return pd.Timestamp(year, 9, 30)
    elif quarter == "4": return pd.Timestamp(year, 12, 31)

def get_ons_gdp_series(series_id):
    URL = f"https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/{series_id}/ukea/data"
    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    data = r.json()
    rows = []
    for obs in data["quarters"]:
        rows.append([quarter_to_date(obs["date"]), float(obs["value"])])
    df = pd.DataFrame(rows, columns=["date", "value"])
    return df.sort_values("date").reset_index(drop=True)

quarterly_gdp = get_ons_gdp_series("IHYQ")
yearly_gdp = get_ons_gdp_series("IHYR")

def write_last_three_gdp(df, row, col):
    latest = df.tail(3).reset_index(drop=True)
    for i, r_val in latest.iterrows():
        wb.update_cell(row, col + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
        wb.update_cell(row, col + (i * 2) + 1, round(r_val["value"], 2))

write_last_three_gdp(quarterly_gdp, 27, 2)
write_last_three_gdp(yearly_gdp, 32, 2)
print("UK GDP quarterly and yearly updated successfully")


# ==============================================================================
# 6. UK RETAIL SALES
# ==============================================================================

print("\nProcessing UK Retail Sales...")
SERIES_ID_RETAIL = "J5EK"
URL_RETAIL = f"https://www.ons.gov.uk/businessindustryandtrade/retailindustry/timeseries/{SERIES_ID_RETAIL}/drsi/data"
r = requests.get(URL_RETAIL, timeout=30)
r.raise_for_status()
data = r.json()

rows = []
for obs in data["months"]:
    rows.append([pd.to_datetime(obs["date"]), float(obs["value"])])
retail = pd.DataFrame(rows, columns=["date", "retail_index"])
retail = retail.sort_values("date").reset_index(drop=True)

retail["retail_monthly"] = (retail["retail_index"] / retail["retail_index"].shift(1) - 1) * 100
retail["retail_yearly"] = (retail["retail_index"] / retail["retail_index"].shift(12) - 1) * 100

quarterly_retail = (
    retail.set_index("date")["retail_index"]
    .resample("QE").mean().pct_change() * 100
)
quarterly_retail = quarterly_retail.reset_index()
quarterly_retail.columns = ["date", "retail_quarterly"]

def write_last_three_cols(df, value_column, row, col):
    latest = df.dropna(subset=[value_column]).tail(3).reset_index(drop=True)
    for i, r_val in latest.iterrows():
        wb.update_cell(row, col + i * 2, r_val["date"].strftime("%Y-%m-%d"))
        wb.update_cell(row, col + i * 2 + 1, round(r_val[value_column], 2))

write_last_three_cols(retail, "retail_monthly", 22, 8)
write_last_three_cols(quarterly_retail, "retail_quarterly", 27, 8)
write_last_three_cols(retail, "retail_yearly", 32, 8)
print("UK Retail Sales updated successfully")


# ==============================================================================
# 7. UK INDUSTRIAL SALES
# ==============================================================================

print("\nProcessing UK Industrial Sales...")
SERIES_ID_IND_SALES = "JT27"
URL_IND_SALES = f"https://www.ons.gov.uk/businessindustryandtrade/manufacturingandproductionindustry/timeseries/{SERIES_ID_IND_SALES}/diop/data"
r = requests.get(URL_IND_SALES, timeout=30)
r.raise_for_status()
data = r.json()

rows = []
for obs in data["months"]:
    rows.append([pd.to_datetime(obs["date"]), float(obs["value"])])
df_ind = pd.DataFrame(rows, columns=["date", "manufacturing_sales"])
df_ind = df_ind.sort_values("date").reset_index(drop=True)

# Monthly
df_ind["monthly_change"] = df_ind["manufacturing_sales"].pct_change() * 100
monthly_ind = df_ind.dropna(subset=["monthly_change"]).tail(3).reset_index(drop=True)

# Quarterly
latest_date_ind = df_ind["date"].max()
completed_quarters_df_ind = df_ind[
    ~((df_ind["date"].dt.year == latest_date_ind.year) & (df_ind["date"].dt.quarter == latest_date_ind.quarter))
]
quarterly_values_ind = completed_quarters_df_ind.set_index("date")["manufacturing_sales"].resample("QE").sum()
quarterly_ind = quarterly_values_ind.pct_change().mul(100).dropna().reset_index()
quarterly_ind.columns = ["date", "quarterly_change"]
quarterly_ind = quarterly_ind.tail(3).reset_index(drop=True)

# Yearly
df_ind["yearly_change"] = df_ind["manufacturing_sales"].pct_change(12) * 100
yearly_ind = df_ind.dropna(subset=["yearly_change"]).tail(3).reset_index(drop=True)

# Write to Sheets (Column Z = 26)
for i, r_val in monthly_ind.iterrows():
    wb.update_cell(22, 26 + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(22, 26 + (i * 2) + 1, round(r_val["monthly_change"], 2))

for i, r_val in quarterly_ind.iterrows():
    wb.update_cell(27, 26 + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(27, 26 + (i * 2) + 1, round(r_val["quarterly_change"], 2))

for i, r_val in yearly_ind.iterrows():
    wb.update_cell(32, 26 + (i * 2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(32, 26 + (i * 2) + 1, round(r_val["yearly_change"], 2))
print("UK Industrial Sales updated successfully")


# ==============================================================================
# 8. UK INDUSTRIAL PRODUCTION
# ==============================================================================

print("\nProcessing UK Industrial Production...")
SERIES_ID_PROD = "K222"
URL_PROD = f"https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries/{SERIES_ID_PROD}/data"
r = requests.get(URL_PROD, timeout=30)
r.raise_for_status()
data = r.json()

rows = []
for obs in data["months"]:
    rows.append([pd.to_datetime(obs["date"]), float(obs["value"])])
df_prod = pd.DataFrame(rows, columns=["date", "industrial_production"])
df_prod = df_prod.sort_values("date").reset_index(drop=True)

df_prod["monthly_change"] = df_prod["industrial_production"].pct_change() * 100
monthly_prod = df_prod.dropna(subset=["monthly_change"]).tail(3).reset_index(drop=True)

quarterly_prod = (
    df_prod.set_index("date")["industrial_production"]
    .resample("QE").mean().pct_change().mul(100).dropna().reset_index()
)
quarterly_prod.columns = ["date", "quarterly_change"]
quarterly_prod = quarterly_prod.tail(3).reset_index(drop=True)

df_prod["yearly_change"] = df_prod["industrial_production"].pct_change(12) * 100
yearly_prod = df_prod.dropna(subset=["yearly_change"]).tail(3).reset_index(drop=True)

# Write to Sheets (Column AF = 32)
for i, r_val in monthly_prod.iterrows():
    wb.update_cell(22, 32 + (i*2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(22, 32 + (i*2)+1, round(r_val["monthly_change"], 2))

for i, r_val in quarterly_prod.iterrows():
    wb.update_cell(27, 32 + (i*2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(27, 32 + (i*2)+1, round(r_val["quarterly_change"], 2))

for i, r_val in yearly_prod.iterrows():
    wb.update_cell(32, 32 + (i*2), r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(32, 32 + (i*2)+1, round(r_val["yearly_change"], 2))
print("UK Industrial Production updated successfully")


# ==============================================================================
# 9. UK PAYROLLED EMPLOYEES
# ==============================================================================

print("\nProcessing UK Payrolled Employees...")
URL_PAYROLL = "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/realtimeinformationstatisticsreferencetableseasonallyadjusted/current/rtisajul2026.xlsx"
r = requests.get(URL_PAYROLL, timeout=60)
r.raise_for_status()

raw_payroll = pd.read_excel(BytesIO(r.content), sheet_name="1. Payrolled employees (UK)", header=None)
df_payroll = raw_payroll.iloc[6:, [0, 1]].copy()
df_payroll.columns = ["date", "payrolled_employees"]
df_payroll["date"] = pd.to_datetime(df_payroll["date"], format="%B %Y", errors="coerce")
df_payroll["payrolled_employees"] = pd.to_numeric(df_payroll["payrolled_employees"], errors="coerce")
df_payroll = df_payroll.dropna().sort_values("date").drop_duplicates("date").reset_index(drop=True)

df_payroll["monthly_change"] = df_payroll["payrolled_employees"].pct_change() * 100
monthly_payroll = df_payroll[["date", "payrolled_employees", "monthly_change"]].dropna(subset=["monthly_change"]).tail(3).reset_index(drop=True)

quarterly_series_payroll = df_payroll.set_index("date")["payrolled_employees"].resample("QE").last()
latest_quarter_payroll = df_payroll["date"].max().to_period("Q")
latest_quarter_rows = df_payroll[df_payroll["date"].dt.to_period("Q") == latest_quarter_payroll]
if len(latest_quarter_rows) < 3:
    quarterly_series_payroll = quarterly_series_payroll.iloc[:-1]
quarterly_payroll = quarterly_series_payroll.pct_change().mul(100).dropna().reset_index()
quarterly_payroll.columns = ["date", "quarterly_change"]
quarterly_payroll = quarterly_payroll.tail(3).reset_index(drop=True)

df_payroll["yearly_change"] = df_payroll["payrolled_employees"].pct_change(12) * 100
yearly_payroll = df_payroll[["date", "payrolled_employees", "monthly_change", "yearly_change"]].dropna(subset=["yearly_change"]).tail(3).reset_index(drop=True)

for i, r_val in monthly_payroll.iterrows():
    wb.update_cell(116, 2 + i * 2, r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(116, 3 + i * 2, round(r_val["monthly_change"], 2))

for i, r_val in quarterly_payroll.iterrows():
    wb.update_cell(121, 2 + i * 2, r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(121, 3 + i * 2, round(r_val["quarterly_change"], 2))

for i, r_val in yearly_payroll.iterrows():
    wb.update_cell(126, 2 + i * 2, r_val["date"].strftime("%Y-%m-%d"))
    wb.update_cell(126, 3 + i * 2, round(r_val["yearly_change"], 2))
print("UK Payrolled Employees updated successfully.")


# ==============================================================================
# 10. UK UNEMPLOYMENT RATE
# ==============================================================================

print("\nProcessing UK Unemployment Rate...")
URL_UNEMP = "https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms"
r = requests.get(URL_UNEMP, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()

raw_unemp = pd.read_csv(StringIO(r.text), header=None)
data_unemp = raw_unemp.iloc[:, :2].copy()
data_unemp.columns = ["period", "value"]
data_unemp["value"] = pd.to_numeric(data_unemp["value"], errors="coerce")
data_unemp = data_unemp.dropna(subset=["value"])
data_unemp["date"] = pd.to_datetime(data_unemp["period"].astype(str), format="%Y %b", errors="coerce")
data_unemp = data_unemp.dropna(subset=["date"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)

monthly_unemp = data_unemp.tail(3)[["date", "value"]].copy()

data_unemp["yearly_change"] = data_unemp["value"].pct_change(12) * 100
yearly_unemp = data_unemp.dropna(subset=["yearly_change"]).tail(3)[["date", "yearly_change"]].copy()
yearly_unemp.columns = ["date", "value"]

data_unemp["quarter"] = data_unemp["date"].dt.to_period("Q")
quarterly_all_unemp = data_unemp.groupby("quarter").last().reset_index()
latest_released_date = data_unemp["date"].max()
quarterly_all_unemp = quarterly_all_unemp[quarterly_all_unemp["quarter"].dt.end_time <= latest_released_date]
quarterly_unemp = quarterly_all_unemp.tail(3)[["quarter", "value"]].copy()
quarterly_unemp["date"] = quarterly_unemp["quarter"].dt.end_time.dt.normalize()
quarterly_unemp = quarterly_unemp[["date", "value"]]

def write_row_unemp(df, row):
    values = []
    for _, r_val in df.iterrows():
        values.extend([r_val["date"].strftime("%Y-%m-%d"), round(float(r_val["value"]), 2)])
    wb.update(range_name=f"H{row}:M{row}", values=[values])

write_row_unemp(monthly_unemp, 116)
write_row_unemp(quarterly_unemp, 121)
write_row_unemp(yearly_unemp, 126)
print("UK Unemployment Rate updated successfully.")


# ==============================================================================
# 11. UK LABOUR FORCE PARTICIPATION
# ==============================================================================

print("\nProcessing UK Labour Force Participation...")
URL_LF = "https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/timeseries/lf2h/lms"
r = requests.get(URL_LF, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()

raw_lf = pd.read_csv(StringIO(r.text), header=None)
data_lf = raw_lf.iloc[:, :2].copy()
data_lf.columns = ["date", "value"]
data_lf["date"] = pd.to_datetime(data_lf["date"], errors="coerce")
data_lf["value"] = pd.to_numeric(data_lf["value"], errors="coerce")
data_lf = data_lf.dropna().sort_values("date").drop_duplicates("date").reset_index(drop=True)

data_lf["monthly_change"] = data_lf["value"].pct_change() * 100
monthly_lf = data_lf.dropna(subset=["monthly_change"]).tail(3).copy()

data_lf["quarter"] = data_lf["date"].dt.to_period("Q")
quarterly_series_lf = data_lf.groupby("quarter")["value"].last().sort_index()
latest_period_lf = data_lf["date"].max().to_period("Q")
quarterly_series_lf = quarterly_series_lf[quarterly_series_lf.index < latest_period_lf]
quarterly_lf = quarterly_series_lf.pct_change().mul(100).dropna().tail(3).reset_index()
quarterly_lf.columns = ["period", "quarterly_change"]
quarterly_lf["date"] = quarterly_lf["period"].dt.end_time.dt.normalize()

data_lf["yearly_change"] = data_lf["value"].pct_change(12) * 100
yearly_lf = data_lf.dropna(subset=["yearly_change"]).tail(3).copy()

def write_to_sheet_lf(df, row, value_col):
    values = []
    for _, r_val in df.iterrows():
        values.extend([r_val["date"].strftime("%Y-%m-%d"), round(float(r_val[value_col]), 2)])
    start_col = 14
    end_col = start_col + len(values) - 1
    def col_letter(n):
        result = ""
        while n:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result
    cell_range = f"{col_letter(start_col)}{row}:{col_letter(end_col)}{row}"
    wb.update(range_name=cell_range, values=[values])

write_to_sheet_lf(monthly_lf, 116, "monthly_change")
write_to_sheet_lf(quarterly_lf, 121, "quarterly_change")
write_to_sheet_lf(yearly_lf, 126, "yearly_change")
print("UK Labour Force Participation % changes updated successfully.")


# ==============================================================================
# 12. UK AVERAGE WEEKLY EARNINGS
# ==============================================================================

print("\nProcessing UK Average Weekly Earnings...")
PAGE_EARN = "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/averageweeklyearningsearn01/current"
r = requests.get(PAGE_EARN, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()

links = re.findall(r'href=["\']([^"\']+\.xls[x]?)["\']', r.text, re.I)
URL_EARN = next(("https://www.ons.gov.uk" + x if x.startswith("/") else x for x in links if "earn01jul2026" in x.lower()), None)

if not URL_EARN:
    print("WARNING: EARN01 XLS not found for the requested criteria.")
else:
    r = requests.get(URL_EARN, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    raw_earn = pd.read_excel(BytesIO(r.content), sheet_name="3. AWE Regular Pay", header=None)
    data_earn = raw_earn.iloc[9:, [0, 1]].copy()
    data_earn.columns = ["date", "value"]
    data_earn["date"] = pd.to_datetime(data_earn["date"], errors="coerce")
    data_earn["value"] = pd.to_numeric(data_earn["value"], errors="coerce")
    data_earn = data_earn.dropna().sort_values("date").drop_duplicates("date").reset_index(drop=True)

    data_earn["monthly_change"] = data_earn["value"].pct_change() * 100
    monthly_earn = data_earn[["date", "monthly_change"]].dropna().tail(3).reset_index(drop=True)

    q_earn = data_earn.set_index("date")["value"].resample("QE").last().dropna()
    latest_q_earn = data_earn["date"].max().to_period("Q")
    q_earn = q_earn[q_earn.index.to_period("Q") < latest_q_earn]
    quarterly_earn = q_earn.pct_change().mul(100).dropna().tail(3).reset_index()
    quarterly_earn.columns = ["date", "quarterly_change"]

    data_earn["yearly_change"] = data_earn["value"].pct_change(12) * 100
    yearly_earn = data_earn[["date", "yearly_change"]].dropna().tail(3).reset_index(drop=True)

    def write_row_earn(df, row, value_col):
        values = []
        for _, r_val in df.iterrows():
            values += [r_val["date"].strftime("%Y-%m-%d"), round(float(r_val[value_col]), 2)]
        start_col = 20
        end_col = start_col + len(values) - 1
        def col_letter(n):
            s = ""
            while n:
                n, rem = divmod(n - 1, 26)
                s = chr(65 + rem) + s
            return s
        cell_range = f"{col_letter(start_col)}{row}:{col_letter(end_col)}{row}"
        wb.update(range_name=cell_range, values=[values])

    write_row_earn(monthly_earn, 116, "monthly_change")
    write_row_earn(quarterly_earn, 121, "quarterly_change")
    write_row_earn(yearly_earn, 126, "yearly_change")
    print("UK Average Weekly Earnings % changes updated successfully.")


# ==============================================================================
# 13. UK CLAIMANT COUNT & VACANCIES
# ==============================================================================

print("\nProcessing UK Claimant Count & Vacancies...")
URL_UNEM_XLS = "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peoplenotinwork/unemployment/datasets/claimantcountandvacanciesdataset/current/unem.xlsx"
r = requests.get(URL_UNEM_XLS, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()
raw_unem_xls = pd.read_excel(BytesIO(r.content), sheet_name="data", header=None)

# 13a. CLAIMANT COUNT
data_claim = raw_unem_xls.iloc[:, [0, 1]].copy()
data_claim.columns = ["date", "value"]
data_claim["date"] = pd.to_datetime(data_claim["date"], format="mixed", errors="coerce")
data_claim["value"] = pd.to_numeric(data_claim["value"], errors="coerce")
data_claim = data_claim.dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)

monthly_claim = data_claim.assign(change=data_claim["value"].pct_change() * 100).dropna().tail(3)[["date", "change"]]

q_claim = data_claim.set_index("date")["value"].resample("QE").last()
if data_claim["date"].max().month not in [3, 6, 9, 12]:
    q_claim = q_claim.iloc[:-1]
quarterly_claim = q_claim.pct_change().mul(100).dropna().tail(3).reset_index()
quarterly_claim.columns = ["date", "change"]

yearly_claim = data_claim.assign(change=data_claim["value"].pct_change(12) * 100).dropna().tail(3)[["date", "change"]]

def write_row_claim(df, row):
    values = []
    for _, r_val in df.iterrows():
        values.extend([r_val["date"].strftime("%Y-%m-%d"), round(float(r_val["change"]), 2)])
    wb.update(range_name=f"Z{row}:AE{row}", values=[values])

write_row_claim(monthly_claim, 116)
write_row_claim(quarterly_claim, 121)
write_row_claim(yearly_claim, 126)
print("UK Claimant Count % changes written to Google Sheets successfully.")

# 13b. VACANCIES (Job Openings)
cols = raw_unem_xls.iloc[0].astype(str)
vac_col = next(i for i, x in cols.items() if "Vacancies" in x and "UK" in x)

data_vac = raw_unem_xls.iloc[:, [0, vac_col]].copy()
data_vac.columns = ["date", "value"]
data_vac["date"] = pd.to_datetime(data_vac["date"], format="mixed", errors="coerce")
data_vac["value"] = pd.to_numeric(data_vac["value"], errors="coerce")
data_vac = data_vac.dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)

monthly_vac = data_vac.assign(change=data_vac["value"].pct_change() * 100).dropna().tail(3)[["date", "change"]]

q_vac = data_vac.set_index("date")["value"].resample("QE").mean().dropna()
last_month = data_vac["date"].max().month
if last_month not in [3, 6, 9, 12]:
    q_vac = q_vac.iloc[:-1]
quarterly_vac = q_vac.pct_change().mul(100).dropna().tail(3).reset_index()
quarterly_vac.columns = ["date", "change"]

yearly_vac = data_vac.assign(change=data_vac["value"].pct_change(12) * 100).dropna().tail(3)[["date", "change"]]

def write_row_vac(df, row):
    values = []
    for _, r_val in df.iterrows():
        values.extend([r_val["date"].strftime("%Y-%m-%d"), round(float(r_val["change"]), 2)])
    wb.update(range_name=f"AF{row}:AK{row}", values=[values])

write_row_vac(monthly_vac, 116)
write_row_vac(quarterly_vac, 121)
write_row_vac(yearly_vac, 126)
print("UK Job Openings / Vacancies % changes written to Google Sheets successfully.")

print("\n--- ALL UK FUNDAMENTAL DATA UPLOADED SUCCESSFULLY ---")
