import sys
import os
import subprocess
import time
import re
import nest_asyncio
import pandas as pd
from bs4 import BeautifulSoup
import fredapi as fa

# =========================
# CONFIGURATION
# =========================
os.environ["CHROME_PATH"] = "/usr/bin/google-chrome"
FRED_API_KEY = '2d406210f6235b1e9f9e750365bcc8b4'
SHEET_TAB_NAME = 'Historical Values Storage'

# Global placeholders
fred = None
client = None
wb = None

# =========================
# RETRY & SLEEP LOGIC WRAPPER
# =========================
def safe_update_cell(row, col, val):
    global wb
    max_retries = 8
    for attempt in range(max_retries):
        try:
            wb.update_cell(row, col, val)
            time.sleep(2.5)  # Paced to ~24 writes/min to strictly prevent 429 limit errors
            return
        except Exception as e:
            if '429' in str(e):
                sleep_time = 10 * (1.5 ** attempt)
                print(f"API 429 Quota Exceeded. Sleeping {sleep_time:.1f}s before retrying...")
                time.sleep(sleep_time)
            else:
                raise e
    print(f"Failed to update cell {row}, {col} after {max_retries} retries.")


# =========================
# SYSTEM SETUP (Colab/Linux)
# =========================
def setup_environment():
    print("Verifying and setting up system environment...")

    try:
        subprocess.run(["sudo", "apt-get", "update", "-y"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["sudo", "apt-get", "install", "-y", "wget", "curl", "unzip"], check=True, stdout=subprocess.DEVNULL)
    except Exception as e:
        print(f"System update warning: {e}")

    try:
        subprocess.run("wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb", shell=True, check=True)
        subprocess.run("sudo dpkg -i google-chrome-stable_current_amd64.deb || true", shell=True)
        subprocess.run("sudo apt-get install -f -y", shell=True, check=True, stdout=subprocess.DEVNULL)
    except Exception as e:
        print(f"Chrome install warning: {e}")

    try:
        subprocess.run(["which", "Xvfb"], check=True, stdout=subprocess.DEVNULL)
    except:
        subprocess.run(["sudo", "apt-get", "install", "-y", "xvfb", "x11-utils"], check=True)

    os.environ['DISPLAY'] = ':99'

    try:
        subprocess.run(["xdpyinfo", "-display", ":99"], check=True, stdout=subprocess.DEVNULL)
    except:
        subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1920x1080x24", "-ac"])
        time.sleep(2)

    required_packages = {
        "seleniumbase": "seleniumbase",
        "pyautogui": "pyautogui",
        "bs4": "beautifulsoup4",
        "nest_asyncio": "nest_asyncio",
        "pandas": "pandas",
        "fredapi": "fredapi"
    }

    for import_name, pip_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", pip_name], check=True)


# =========================
# SCRAPING FUNCTIONS
# =========================
def scrape_ism_services_history():
    print("\n--- Scraping ISM Services PMI ---")
    url = "https://www.forexfactory.com/calendar/253-us-ism-services-pmi"
    try:
        from seleniumbase import SB
        with SB(uc=True, headless=False, xvfb=True) as sb:
            sb.uc_open_with_reconnect(url, 6)
            sb.uc_gui_click_captcha()
            sb.sleep(3)
            
            for i in range(4):
                if sb.is_link_text_visible("More"):
                    try:
                        sb.click_link_text("More")
                    except Exception:
                        # Fallback: Hide any floating banner overlay that intercepts the click, then try again
                        sb.execute_script("""
                            var overlays = document.querySelectorAll('.anchor-banner__content');
                            overlays.forEach(function(el) { el.style.display = 'none'; });
                        """)
                        sb.sleep(1)
                        sb.click_link_text("More")
                    sb.sleep(3)
            html_source = sb.get_page_source()
    except Exception as e:
        print("Scraping failed:", e)
        return

    soup = BeautifulSoup(html_source, 'html.parser')
    history_rows = []
    date_pattern = re.compile(r'([A-Za-z]{3,4}\s+\d{1,2},\s+\d{4})')
    header_el = soup.find(string=re.compile(r'Expected Impact\s*/\s*Date', re.IGNORECASE))
    container = None

    if header_el:
        parent = header_el.parent
        for _ in range(5):
            if parent and len(parent.get_text()) > 200:
                container = parent
                break
            parent = parent.parent

    if container:
        text_blocks = [s.strip() for s in container.strings if s.strip()]
        for i, block in enumerate(text_blocks):
            if date_pattern.search(block):
                date_val = date_pattern.search(block).group(1)
                row_values = []
                for j in range(i + 1, min(i + 8, len(text_blocks))):
                    if date_pattern.search(text_blocks[j]):
                        break
                    if "Impact Expected" in text_blocks[j]:
                        continue
                    row_values.append(text_blocks[j])
                    if len(row_values) == 3:
                        break
                while len(row_values) < 3:
                    row_values.append("-")
                history_rows.append([
                    "US ISM Services PMI", "USD", date_val, row_values[0], row_values[1], row_values[2]
                ])

    if not history_rows:
        print("No data found.")
        return

    df = pd.DataFrame(history_rows, columns=["Title", "Country", "Release Date", "Actual", "Forecast", "Previous"])
    df['Release Date'] = pd.to_datetime(df['Release Date'], errors='coerce')
    df['Actual'] = pd.to_numeric(df['Actual'], errors='coerce')
    df = df.dropna(subset=['Release Date', 'Actual'])
    df = df.sort_values('Release Date').reset_index(drop=True)

    df["PMI_%_change"] = df["Actual"].pct_change() * 100
    monthly = df[["Release Date", "PMI_%_change"]].dropna().tail(3).reset_index(drop=True)

    if len(monthly) < 3:
        print("Not enough data for fixed cell update.")
        return

    global wb
    safe_update_cell(20, 14, monthly.iloc[0]["Release Date"].strftime("%Y-%m-%d"))
    safe_update_cell(20, 15, round(monthly.iloc[0]["PMI_%_change"], 2))
    safe_update_cell(20, 16, monthly.iloc[1]["Release Date"].strftime("%Y-%m-%d"))
    safe_update_cell(20, 17, round(monthly.iloc[1]["PMI_%_change"], 2))
    safe_update_cell(20, 18, monthly.iloc[2]["Release Date"].strftime("%Y-%m-%d"))
    safe_update_cell(20, 19, round(monthly.iloc[2]["PMI_%_change"], 2))
    print(monthly)
    print("US ISM Services PMI % change updated successfully.")


def scrape_ism_manufacturing_history():
    print("\n--- Scraping ISM Manufacturing PMI ---")
    url = "https://www.forexfactory.com/calendar/252-us-ism-manufacturing-pmi"
    try:
        from seleniumbase import SB
        with SB(uc=True, headless=False, xvfb=True) as sb:
            sb.uc_open_with_reconnect(url, 6)
            sb.uc_gui_click_captcha()
            sb.sleep(3)
            
            for i in range(4):
                if sb.is_link_text_visible("More"):
                    try:
                        sb.click_link_text("More")
                    except Exception:
                        # Fallback: Hide any floating banner overlay that intercepts the click, then try again
                        sb.execute_script("""
                            var overlays = document.querySelectorAll('.anchor-banner__content');
                            overlays.forEach(function(el) { el.style.display = 'none'; });
                        """)
                        sb.sleep(1)
                        sb.click_link_text("More")
                    sb.sleep(3)
            html_source = sb.get_page_source()
    except Exception as e:
        print("Scraping failed:", e)
        return

    soup = BeautifulSoup(html_source, 'html.parser')
    history_rows = []
    date_pattern = re.compile(r'([A-Za-z]{3,4}\s+\d{1,2},\s+\d{4})')
    header_el = soup.find(string=re.compile(r'Expected Impact\s*/\s*Date', re.IGNORECASE))
    container = None

    if header_el:
        parent = header_el.parent
        for _ in range(5):
            if parent and len(parent.get_text()) > 200:
                container = parent
                break
            parent = parent.parent

    if container:
        text_blocks = [s.strip() for s in container.strings if s.strip()]
        for i, block in enumerate(text_blocks):
            if date_pattern.search(block):
                date_val = date_pattern.search(block).group(1)
                row_values = []
                for j in range(i + 1, min(i + 8, len(text_blocks))):
                    if date_pattern.search(text_blocks[j]):
                        break
                    if "Impact Expected" in text_blocks[j]:
                        continue
                    row_values.append(text_blocks[j])
                    if len(row_values) == 3:
                        break
                while len(row_values) < 3:
                    row_values.append("-")
                history_rows.append([
                    "US ISM Manufacturing PMI", "USD", date_val, row_values[0], row_values[1], row_values[2]
                ])

    if not history_rows:
        print("No data found.")
        return

    df = pd.DataFrame(history_rows, columns=["Title", "Country", "Release Date", "Actual", "Forecast", "Previous"])
    df['Release Date'] = pd.to_datetime(df['Release Date'], errors='coerce')
    df['Actual'] = pd.to_numeric(df['Actual'], errors='coerce')
    df = df.dropna(subset=['Release Date', 'Actual'])
    df = df.sort_values('Release Date')

    monthly = df[['Release Date', 'Actual']].tail(3).reset_index(drop=True)

    if len(monthly) < 3:
        print("Not enough data for fixed cell update.")
        return

    global wb
    safe_update_cell(20, 20, monthly.iloc[0]['Release Date'].strftime('%Y-%m-%d'))
    safe_update_cell(20, 21, monthly.iloc[0]['Actual'])
    safe_update_cell(20, 22, monthly.iloc[1]['Release Date'].strftime('%Y-%m-%d'))
    safe_update_cell(20, 23, monthly.iloc[1]['Actual'])
    safe_update_cell(20, 24, monthly.iloc[2]['Release Date'].strftime('%Y-%m-%d'))
    safe_update_cell(20, 25, monthly.iloc[2]['Actual'])
    print("Fixed-cell update complete (Manufacturing PMI).")


# =========================
# MAIN EXECUTION
# =========================
if __name__ == "__main__":
    setup_environment()
    nest_asyncio.apply()

    print("Authenticating FRED and Google Sheets APIs...")
    fred = fa.Fred(FRED_API_KEY)
    
    # ==========================================
    # API AUTHENTICATION
    # ==========================================
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "google-api-python-client", "google-auth-httplib2", "google-auth-oauthlib", "gspread"], check=True)
    
    import gspread
    from google.oauth2.service_account import Credentials
    
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    
    creds = Credentials.from_service_account_file("forexdailybias-5ce3a8ede6c9.json", scopes=scopes)
    client = gspread.authorize(creds)
    
    sheet_id = "1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU"
    sheet = client.open_by_key(sheet_id)
    wb = sheet.worksheet(SHEET_TAB_NAME)
    
    wb.resize(rows=150, cols=50)
    # ==========================================

    # -------------------------------------------------------------------------
    # FRED INDICATORS
    # -------------------------------------------------------------------------

    series_data = [
        ("CPILFESL", 2, 3, 7, 3, 12, 3),
        ("CPIAUCSL", 2, 9, 7, 9, 12, 9),
        ("PPIFID", 2, 15, 7, 15, 12, 15),
        ("PPIFES", 2, 21, 7, 21, 12, 21),
        ("PCEPI", 2, 27, 7, 27, 12, 27),
        ("PCEPILFE", 2, 33, 7, 33, 12, 33)
    ]

    for ticker, m_row, m_col, q_row, q_col, y_row, y_col in series_data:
        print(f"\nProcessing {ticker}...")
        
        # Monthly values (Fresh pull)
        df_m = fred.get_series(ticker).to_frame(name="index").dropna()
        df_m["yoy"] = df_m["index"].pct_change(1, fill_method=None) * 100
        latestm = df_m.tail(3).reset_index()
        latestm.columns = ["date", "index", "yoy"]
        for i in range(3):
            datem = latestm.loc[i, "date"].strftime("%Y-%m-%d")
            mom = float(latestm.loc[i, "yoy"])
            safe_update_cell(m_row, (m_col - 1) + (i * 2), datem)
            safe_update_cell(m_row, m_col + (i * 2), mom)

        # Quarterly values (Fresh pull)
        df_q = fred.get_series(ticker).to_frame(name="index").dropna()
        quarter_df = df_q[df_q.index.month.isin([3, 6, 9, 12])].copy()
        quarter_df["quarterly"] = quarter_df["index"].pct_change(fill_method=None) * 100
        quarter_df = quarter_df.dropna()
        latestq = quarter_df.tail(3).reset_index()
        latestq.columns = ["date", "index", "quarterly"]
        for i in range(3):
            dateq = latestq.loc[i, "date"].strftime("%Y-%m-%d")
            valueq = float(latestq.loc[i, "quarterly"])
            safe_update_cell(q_row, (q_col - 1) + (i * 2), dateq)
            safe_update_cell(q_row, q_col + (i * 2), valueq)

        # Yearly values (Fresh pull)
        df_y = fred.get_series(ticker).to_frame(name="index").dropna()
        df_y["yoy"] = df_y["index"].pct_change(12, fill_method=None) * 100
        df_y = df_y.dropna()
        latest = df_y.tail(3).reset_index()
        latest.columns = ["date", "index", "yoy"]
        for i in range(3):
            date = latest.loc[i, "date"].strftime("%Y-%m-%d")
            yoy = float(latest.loc[i, "yoy"])
            safe_update_cell(y_row, (y_col - 1) + (i * 2), date)
            safe_update_cell(y_row, y_col + (i * 2), yoy)

    # GDP
    print("\nProcessing GDP...")
    gdp = fred.get_series("GDPC1").dropna().to_frame("level")
    gdp["qoq"] = gdp["level"].pct_change(fill_method=None) * 100
    gdp["annualised_qoq"] = ((1 + gdp["qoq"] / 100) ** 4 - 1) * 100
    gdp.index = gdp.index + pd.offsets.QuarterEnd(0)
    gdp = gdp.dropna()
    latest = gdp.tail(3)
    for i in range(len(latest)):
        date = latest.index[i].strftime("%Y-%m-%d")
        qoq = float(latest["annualised_qoq"].iloc[i])
        safe_update_cell(25, 2 + (i * 2), date)
        safe_update_cell(25, 3 + (i * 2), qoq)

    gdp_y = fred.get_series("GDPC1").to_frame(name="level").dropna().sort_index()
    gdp_y["yoy"] = gdp_y["level"].pct_change(4) * 100
    gdp_y.index = gdp_y.index + pd.offsets.QuarterEnd(0)
    latest_y = gdp_y.dropna().tail(3)
    for i in range(len(latest_y)):
        date = latest_y.index[i].strftime("%Y-%m-%d")
        yoy = float(latest_y["yoy"].iloc[i])
        safe_update_cell(30, 2 + (i * 2), date)
        safe_update_cell(30, 3 + (i * 2), yoy)

    # Retail Sales
    print("\nProcessing Retail Sales...")
    df_m = fred.get_series("RSAFS").to_frame(name="level").dropna().sort_index()
    df_m["mom"] = df_m["level"].pct_change(1) * 100
    latest = df_m.dropna().tail(3).reset_index()
    latest.columns = ["date", "level", "mom"]
    for i in range(len(latest)):
        date = latest.loc[i, "date"].strftime("%Y-%m-%d")
        mom = float(latest.loc[i, "mom"])
        safe_update_cell(20, 8 + (i * 2), date)
        safe_update_cell(20, 9 + (i * 2), mom)

    df_q = fred.get_series("RSAFS").to_frame(name="level").dropna().sort_index()
    last_month = df_q.index.max()
    q = df_q.resample("QE").last()
    q = q[q.index <= last_month]
    q["qoq"] = q["level"].pct_change() * 100
    latest = q.dropna().tail(3).reset_index()
    latest.columns = ["date", "level", "qoq"]
    for i in range(len(latest)):
        date = latest.loc[i, "date"].strftime("%Y-%m-%d")
        qoq = float(latest.loc[i, "qoq"])
        safe_update_cell(25, 8 + (i * 2), date)
        safe_update_cell(25, 9 + (i * 2), qoq)

    df_y = fred.get_series("RSAFS").to_frame(name="level").dropna().sort_index()
    df_y["yoy"] = df_y["level"].pct_change(12) * 100
    latest = df_y.dropna().tail(3).reset_index()
    latest.columns = ["date", "level", "yoy"]
    for i in range(len(latest)):
        date = latest.loc[i, "date"].strftime("%Y-%m-%d")
        yoy = float(latest.loc[i, "yoy"])
        safe_update_cell(30, 8 + (i * 2), date)
        safe_update_cell(30, 9 + (i * 2), yoy)

    # AMTMNO
    print("\nProcessing AMTMNO...")
    df_m = fred.get_series("AMTMNO").to_frame(name="level").dropna().sort_index()
    df_m["mom"] = df_m["level"].pct_change(fill_method=None) * 100
    latest = df_m.dropna().tail(3).reset_index()
    latest.columns = ["date", "level", "mom"]
    for i in range(len(latest)):
        date = latest.loc[i, "date"].strftime("%Y-%m-%d")
        mom = float(latest.loc[i, "mom"])
        safe_update_cell(20, 26 + (i * 2), date)
        safe_update_cell(20, 27 + (i * 2), mom)

    df_q = fred.get_series("AMTMNO").to_frame(name="level").dropna().sort_index()
    q = df_q.resample("QE").last()
    q = q[q.index <= df_q.index.max()]
    q["qoq"] = q["level"].pct_change(fill_method=None) * 100
    latest = q.dropna().tail(3).reset_index()
    latest.columns = ["date", "level", "qoq"]
    for i in range(len(latest)):
        date = latest.loc[i, "date"].strftime("%Y-%m-%d")
        qoq = float(latest.loc[i, "qoq"])
        safe_update_cell(25, 26 + (i * 2), date)
        safe_update_cell(25, 27 + (i * 2), qoq)

    df_y = fred.get_series("AMTMNO").to_frame(name="level").dropna().sort_index()
    df_y["yoy"] = df_y["level"].pct_change(12) * 100
    latest = df_y.dropna().tail(3).reset_index()
    latest.columns = ["date", "level", "yoy"]
    for i in range(len(latest)):
        date = latest.loc[i, "date"].strftime("%Y-%m-%d")
        yoy = float(latest.loc[i, "yoy"])
        safe_update_cell(30, 26 + (i * 2), date)
        safe_update_cell(30, 27 + (i * 2), yoy)

    INDSalesGet = fred.get_series('AMTMNO')
    INDSales = INDSalesGet.tail()
    safe_update_cell(20, 32, INDSales.index[2].strftime('%Y-%m-%d'))
    safe_update_cell(20, 33, INDSales.iloc[2])
    safe_update_cell(20, 34, INDSales.index[3].strftime('%Y-%m-%d'))
    safe_update_cell(20, 35, INDSales.iloc[3])
    safe_update_cell(20, 36, INDSales.index[4].strftime('%Y-%m-%d'))
    safe_update_cell(20, 37, INDSales.iloc[4])

    INDSales_Q = INDSalesGet.resample('QE').last()
    safe_update_cell(25, 36, INDSales_Q.index[-2].strftime('%Y-%m-%d'))
    safe_update_cell(25, 37, INDSales_Q.iloc[-2])
    safe_update_cell(25, 34, INDSales_Q.index[-3].strftime('%Y-%m-%d'))
    safe_update_cell(25, 35, INDSales_Q.iloc[-3])
    safe_update_cell(25, 32, INDSales_Q.index[-4].strftime('%Y-%m-%d'))
    safe_update_cell(25, 33, INDSales_Q.iloc[-4])

    INDSales_Y = INDSalesGet.resample('YE').last()
    safe_update_cell(30, 36, INDSales_Y.index[-2].strftime('%Y-%m-%d'))
    safe_update_cell(30, 37, INDSales_Y.iloc[-2])
    safe_update_cell(30, 34, INDSales_Y.index[-3].strftime('%Y-%m-%d'))
    safe_update_cell(30, 35, INDSales_Y.iloc[-3])
    safe_update_cell(30, 32, INDSales_Y.index[-4].strftime('%Y-%m-%d'))
    safe_update_cell(30, 33, INDSales_Y.iloc[-4])

    # INDPRO
    print("\nProcessing INDPRO...")
    df_m = fred.get_series("INDPRO").to_frame(name="level").dropna().sort_index()
    df_m["mom"] = df_m["level"].pct_change(fill_method=None) * 100
    latest = df_m.dropna().tail(3).reset_index()
    latest.columns = ["date", "level", "mom"]
    for i in range(len(latest)):
        safe_update_cell(20, 32 + (i * 2), latest.loc[i, "date"].strftime("%Y-%m-%d"))
        safe_update_cell(20, 33 + (i * 2), float(latest.loc[i, "mom"]))

    df_q = fred.get_series("INDPRO").to_frame(name="level").dropna().sort_index()
    q = df_q.resample("QE").last()
    q = q[q.index <= df_q.index.max()]
    q["qoq"] = q["level"].pct_change(fill_method=None) * 100
    latest = q.dropna().tail(3).reset_index()
    latest.columns = ["date", "level", "qoq"]
    for i in range(len(latest)):
        safe_update_cell(25, 32 + (i * 2), latest.loc[i, "date"].strftime("%Y-%m-%d"))
        safe_update_cell(25, 33 + (i * 2), float(latest.loc[i, "qoq"]))

    df_y = fred.get_series("INDPRO").to_frame(name="level").dropna().sort_index()
    df_y["yoy"] = df_y["level"].pct_change(12, fill_method=None) * 100
    latest = df_y.dropna().tail(3).reset_index()
    latest.columns = ["date", "level", "yoy"]
    for i in range(len(latest)):
        safe_update_cell(30, 32 + (i * 2), latest.loc[i, "date"].strftime("%Y-%m-%d"))
        safe_update_cell(30, 33 + (i * 2), float(latest.loc[i, "yoy"]))

    INDProdGet = fred.get_series('INDPRO')
    INDProd = INDProdGet.tail()
    safe_update_cell(20, 38, INDProd.index[2].strftime('%Y-%m-%d'))
    safe_update_cell(20, 39, INDProd.iloc[2])
    safe_update_cell(20, 40, INDProd.index[3].strftime('%Y-%m-%d'))
    safe_update_cell(20, 41, INDProd.iloc[3])
    safe_update_cell(20, 42, INDProd.index[4].strftime('%Y-%m-%d'))
    safe_update_cell(20, 43, INDProd.iloc[4])

    # Employment & Others
    employment_series = [
        ("PAYEMS", 2, True),
        ("UNRATE", 8, False),
        ("CIVPART", 14, False),
        ("CES0500000003", 20, False)
    ]
    
    for ticker, base_col, is_diff in employment_series:
        print(f"\nProcessing {ticker}...")
        df_m = fred.get_series(ticker).to_frame(name="level").dropna()
        if is_diff:
            df_m["change"] = df_m["level"].diff()
            df_m = df_m.dropna()
            latest = df_m.tail(3).reset_index()
            latest.columns = ["date", "level", "change"]
            for i in range(len(latest)):
                safe_update_cell(114, base_col + (i * 2), latest.loc[i, "date"].strftime("%Y-%m-%d"))
                safe_update_cell(114, (base_col + 1) + (i * 2), f"'{int(latest.loc[i, 'change']):+d}K")
        else:
            latest = df_m.tail(3).reset_index()
            latest.columns = ["date", "level"]
            for i in range(len(latest)):
                safe_update_cell(114, base_col + (i * 2), latest.loc[i, "date"].strftime("%Y-%m-%d"))
                safe_update_cell(114, (base_col + 1) + (i * 2), latest.loc[i, "level"])
        
        df_q = fred.get_series(ticker).to_frame(name="level").dropna().sort_index()
        q = df_q.resample("QE").last().iloc[:-1].dropna()
        if is_diff:
            q["change"] = q["level"].diff()
            q = q.dropna()
            latest = q.tail(3).reset_index()
            latest.columns = ["date", "level", "change"]
            for i in range(len(latest)):
                safe_update_cell(119, base_col + (i * 2), latest.loc[i, "date"].strftime("%Y-%m-%d"))
                safe_update_cell(119, (base_col + 1) + (i * 2), f"'{int(latest.loc[i, 'change']):+d}K")
        else:
            latest = q.tail(3).reset_index()
            latest.columns = ["date", "level"]
            for i in range(len(latest)):
                safe_update_cell(119, base_col + (i * 2), latest.loc[i, "date"].strftime("%Y-%m-%d"))
                safe_update_cell(119, (base_col + 1) + (i * 2), latest.loc[i, "level"])

        df_y = fred.get_series(ticker).to_frame(name="level").dropna().sort_index()
        if is_diff:
            df_y["yoy_change"] = df_y["level"].diff(12)
            df_y = df_y.dropna()
            latest = df_y.tail(3).reset_index()
            latest.columns = ["date", "level", "yoy_change"]
            for i in range(len(latest)):
                safe_update_cell(124, base_col + (i * 2), latest.loc[i, "date"].strftime("%Y-%m-%d"))
                safe_update_cell(124, (base_col + 1) + (i * 2), f"'{int(latest.loc[i, 'yoy_change']):+d}K")
        else:
            latest_month = df_y.index[-1].month
            same_month = df_y[df_y.index.month == latest_month]
            latest = same_month.tail(3).reset_index()
            latest.columns = ["date", "level"]
            for i in range(len(latest)):
                safe_update_cell(124, base_col + (i * 2), latest.loc[i, "date"].strftime("%Y-%m-%d"))
                safe_update_cell(124, (base_col + 1) + (i * 2), round(latest.loc[i, "level"], 1))

    # Extended series handling blocks
    for ticker, offsets in [("CIVPART", [14,16,18, 14,16,18, 14,16,18]), 
                            ("ICSA", [30,28,26, 30,28,26, 30,28,26]),
                            ("JTSJOL", [32,34,36, 36,34,32, 36,34,32])]:
        print(f"\nProcessing Extended {ticker}...")
        VarGet = fred.get_series(ticker)
        
        # Monthly/Raw tail mapping
        if ticker in ["ICSA", "JTSJOL"]:
            Var = VarGet.resample("ME").last() if ticker == "ICSA" else VarGet.tail()
            idx2, idx3, idx4 = -2, -3, -4
            if ticker == "JTSJOL":
                idx2, idx3, idx4 = 2, 3, 4
            safe_update_cell(114, offsets[0], Var.index[idx2].strftime('%Y-%m-%d'))
            safe_update_cell(114, offsets[0]+1, Var.iloc[idx2])
            safe_update_cell(114, offsets[1], Var.index[idx3].strftime('%Y-%m-%d'))
            safe_update_cell(114, offsets[1]+1, Var.iloc[idx3])
            safe_update_cell(114, offsets[2], Var.index[idx4].strftime('%Y-%m-%d'))
            safe_update_cell(114, offsets[2]+1, Var.iloc[idx4])
        else: 
            Var = VarGet.tail()
            safe_update_cell(114, 14, Var.index[2].strftime('%Y-%m-%d'))
            safe_update_cell(114, 15, Var.iloc[2])
            safe_update_cell(114, 16, Var.index[3].strftime('%Y-%m-%d'))
            safe_update_cell(114, 17, Var.iloc[3])
            safe_update_cell(114, 18, Var.index[4].strftime('%Y-%m-%d'))
            safe_update_cell(114, 19, Var.iloc[4])

        # Quarterly mapping
        VarQ = VarGet.resample('QE').last()
        safe_update_cell(119, offsets[3], VarQ.index[-2].strftime('%Y-%m-%d'))
        safe_update_cell(119, offsets[3]+1, VarQ.iloc[-2])
        safe_update_cell(119, offsets[4], VarQ.index[-3].strftime('%Y-%m-%d'))
        safe_update_cell(119, offsets[4]+1, VarQ.iloc[-3])
        safe_update_cell(119, offsets[5], VarQ.index[-4].strftime('%Y-%m-%d'))
        safe_update_cell(119, offsets[5]+1, VarQ.iloc[-4])

        # Yearly mapping
        VarY = VarGet.resample('YE').last()
        safe_update_cell(124, offsets[6], VarY.index[-2].strftime('%Y-%m-%d'))
        safe_update_cell(124, offsets[6]+1, VarY.iloc[-2])
        safe_update_cell(124, offsets[7], VarY.index[-3].strftime('%Y-%m-%d'))
        safe_update_cell(124, offsets[7]+1, VarY.iloc[-3])
        safe_update_cell(124, offsets[8], VarY.index[-4].strftime('%Y-%m-%d'))
        safe_update_cell(124, offsets[8]+1, VarY.iloc[-4])

    # Execute Web Scrapers
    scrape_ism_services_history()
    scrape_ism_manufacturing_history()

    print("Complete!")
