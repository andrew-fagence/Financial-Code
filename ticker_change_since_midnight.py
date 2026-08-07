import subprocess

def main():
    print("Installing Node.js dependencies...")
    subprocess.run(["npm", "install", "@mathieuc/tradingview", "googleapis"], check=True)

    # We use a raw string (r"") to write the JavaScript file exactly as you wrote it
    # Note: 'keyFile' has been updated to match the dynamically generated GitHub Secret file.
    js_code = r"""
const TradingView = require('@mathieuc/tradingview');
const { google } = require('googleapis');

const client = new TradingView.Client();

// =====================================================
// SYMBOL CONFIGURATION
// =====================================================

const configs = [
    { symbol: 'TVC:DXY', row: 53 },
    { symbol: 'FX:JPYBASKET', row: 54 },
    { symbol: 'FX:EURGBP', row: 55 },
    { symbol: 'OANDA:EURUSD', row: 56 },
    { symbol: 'OANDA:GBPUSD', row: 57 },
    { symbol: 'OANDA:EURJPY', row: 58 },
    { symbol: 'OANDA:GBPJPY', row: 59 },
    { symbol: 'TVC:US02Y', row: 60 },
    { symbol: 'TVC:US10Y', row: 61 },
    { symbol: 'CAPITALCOM:US500', row: 62 },
    { symbol: 'CAPITALCOM:US100', row: 63 },
    { symbol: 'CAPITALCOM:GER40', row: 64 },
    { symbol: 'CAPITALCOM:VIX', row: 65 },
    { symbol: 'TVC:USOIL', row: 66 },
    { symbol: 'OANDA:XAUUSD', row: 67 },
    { symbol: 'OANDA:XAGUSD', row: 68 },
    { symbol: 'CRYPTO:BTCUSD', row: 69 }
];

// =====================================================
// GOOGLE SHEETS AUTH
// =====================================================

const auth = new google.auth.GoogleAuth({
    keyFile: 'gcp_credentials.json', // Updated to pull from GitHub Actions Secret
    scopes: ['https://www.googleapis.com/auth/spreadsheets']
});

const spreadsheetId = '1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU';

// =====================================================
// WRITE TO SHEET
// =====================================================

async function writeToSheet(row, midnightPrice) {
    const sheets = google.sheets({ version: 'v4', auth });

    await sheets.spreadsheets.values.update({
        spreadsheetId,
        range: `Sheet1!M${row}`,
        valueInputOption: 'USER_ENTERED',
        requestBody: { values: [[midnightPrice]] }
    });

    console.log(`Google Sheets updated for row ${row} with price: ${midnightPrice}`);
}

// =====================================================
// PROCESS SYMBOL
// =====================================================

async function processSymbol(symbol, row) {
    return new Promise((resolve) => {
        console.log(`\n================================`);
        console.log(`PROCESSING ${symbol}`);
        console.log(`================================`);

        let finished = false;
        const chart = new client.Session.Chart();

        // TradingView calculates daily Change and Change % from the Previous Daily Close.
        // Using the '1D' timeframe gives us exact session closes for each specific asset.
        chart.setMarket(symbol, { timeframe: '1D' });

        chart.onUpdate(async () => {
            if (finished) return;
            
            // Ensure we have at least 2 daily candles (the current ongoing one and the previous completed one)
            if (!chart.periods || chart.periods.length < 2) return;

            // periods[length - 1] is the current ongoing daily bar
            // periods[length - 2] is the previous completed daily bar (TradingView's baseline for change %)
            const previousDailyBar = chart.periods[chart.periods.length - 2];
            
            // The starting point for daily change is exactly the previous day's close
            const startingPrice = previousDailyBar.close;

            finished = true;

            if (startingPrice !== undefined && startingPrice !== null) {
                console.log(`\n${symbol} TRADINGVIEW DAILY STARTING POINT`);
                console.log(`Previous Daily Close Price: ${startingPrice}`);
                await writeToSheet(row, startingPrice);
            } else {
                console.log(`\n${symbol} TRADINGVIEW DAILY STARTING POINT`);
                console.log('Previous Daily Close Price: undefined (No candle found)');
            }

            if (typeof chart.delete === 'function') chart.delete();
            resolve();
        });
    });
}

// =====================================================
// MAIN
// =====================================================

(async () => {
    for (const config of configs) {
        await processSymbol(config.symbol, config.row);
    }
    client.end();
    console.log('\nALL SYMBOLS COMPLETE');
})();
"""
    # Write the script to an isolated temporary file to avoid overriding your existing bot.js
    with open("temp_bot_runner.js", "w") as f:
        f.write(js_code)

    print("Running the Node script...")
    subprocess.run(["node", "temp_bot_runner.js"], check=True)

if __name__ == "__main__":
    main()
