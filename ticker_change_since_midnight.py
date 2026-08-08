import subprocess

def main():
    print("Installing Node.js dependencies...")
    subprocess.run(["npm", "install", "@mathieuc/tradingview", "googleapis"], check=True)

    # We use a raw string (r"") to write the JavaScript file exactly as configured
    # Note: 'keyFile' uses 'gcp_credentials.json' from your GitHub Secret configuration.
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
    keyFile: 'gcp_credentials.json',
    scopes: ['https://www.googleapis.com/auth/spreadsheets']
});

const spreadsheetId = '1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU';

// =====================================================
// WRITE TO SHEET
// =====================================================

async function writeToSheet(row, price) {
    const sheets = google.sheets({ version: 'v4', auth });

    await sheets.spreadsheets.values.update({
        spreadsheetId,
        range: `Sheet1!M${row}`,
        valueInputOption: 'USER_ENTERED',
        requestBody: { values: [[price]] }
    });

    console.log(`Google Sheets updated for row ${row} with price: ${price}`);
}

// =====================================================
// HELPER: FORMAT UTC DATE (YYYY-MM-DD)
// =====================================================

function getUTCDateString(timestampMs) {
    const d = new Date(timestampMs);
    return `${d.getUTCFullYear()}-${(d.getUTCMonth() + 1).toString().padStart(2, '0')}-${d.getUTCDate().toString().padStart(2, '0')}`;
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

        chart.setMarket(symbol, { timeframe: '1D' });

        chart.onUpdate(async () => {
            if (finished) return;

            // Ensure historical daily candles are loaded
            if (!chart.periods || chart.periods.length < 2) return;

            finished = true;

            // Sort candles chronologically by timestamp ascending
            // sortedCandles[length - 1] = Current active/live daily candle
            // sortedCandles[length - 2] = Previous completed daily candle (Close price = Previous Day Close)
            const sortedCandles = [...chart.periods].sort((a, b) => a.time - b.time);
            const prevDailyCandle = sortedCandles[sortedCandles.length - 2];
            const prevDailyClose = prevDailyCandle.close;

            console.log(`\n${symbol} PREVIOUS DAILY CLOSE`);
            console.log(`Previous Daily Candle Date (UTC): ${getUTCDateString(prevDailyCandle.time * 1000)}`);
            console.log(`Previous Daily Close Price: ${prevDailyClose}`);
            await writeToSheet(row, prevDailyClose);

            if (typeof chart.delete === 'function') chart.delete();
            resolve();
        });

        // Fallback timeout in case of slow websocket update
        setTimeout(async () => {
            if (!finished) {
                finished = true;
                console.log(`\n${symbol} CHART TIMEOUT`);

                if (chart.periods && chart.periods.length >= 2) {
                    const sortedCandles = [...chart.periods].sort((a, b) => a.time - b.time);
                    const prevDailyCandle = sortedCandles[sortedCandles.length - 2];
                    const prevDailyClose = prevDailyCandle.close;

                    console.log(`Using Fallback Previous Daily Close Price: ${prevDailyClose}`);
                    await writeToSheet(row, prevDailyClose);
                } else if (chart.periods && chart.periods.length === 1) {
                    const prevDailyClose = chart.periods[0].close;
                    console.log(`Using Fallback Daily Close Price: ${prevDailyClose}`);
                    await writeToSheet(row, prevDailyClose);
                } else {
                    console.log(`No valid chart data found for ${symbol}.`);
                }

                if (typeof chart.delete === 'function') chart.delete();
                resolve();
            }
        }, 8000);
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

    # Write the script to an isolated temporary file to execute
    with open("temp_bot_runner.js", "w") as f:
        f.write(js_code)

    print("Running the Node script...")
    subprocess.run(["node", "temp_bot_runner.js"], check=True)

if __name__ == "__main__":
    main()
