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
        
        // TradingView Watchlists use real-time Quote data (not Chart data) to calculate daily Chg and Chg%.
        // By fetching the Last Price (lp) and Change (ch), we can flawlessly reconstruct the baseline.
        const quote = new client.Session.Quote({ fields: ['lp', 'ch', 'prev_close_price'] });

        if (typeof quote.setFields === 'function') {
            quote.setFields(['lp', 'ch', 'prev_close_price']);
        }

        if (typeof quote.setMarket === 'function') {
            quote.setMarket(symbol);
        } else if (typeof quote.addMarket === 'function') {
            quote.addMarket(symbol);
        }

        const quoteData = {};

        const handleData = async (data) => {
            if (finished) return;
            
            // Ensure we are catching data for the right symbol
            if (data && data.symbol && data.symbol !== symbol) return;

            // Accumulate incoming payload properties
            if (data) {
                if (data.update) {
                    Object.assign(quoteData, data.update);
                } else {
                    Object.assign(quoteData, data);
                }
            }

            // The absolute exact starting point for daily change % on the Watchlist is lp - ch.
            let startingPrice = quoteData.prev_close_price;
            
            if (quoteData.lp !== undefined && quoteData.ch !== undefined) {
                startingPrice = quoteData.lp - quoteData.ch;
                // Fix standard JavaScript floating-point artifacts (e.g. 0.8565699999999 becomes 0.85657)
                startingPrice = parseFloat(startingPrice.toFixed(8));
            }

            // Once we secure the starting price, log it and send it to the spreadsheet
            if (startingPrice !== undefined && startingPrice !== null && !isNaN(startingPrice)) {
                finished = true;
                console.log(`\n${symbol} TRADINGVIEW WATCHLIST STARTING POINT`);
                console.log(`Last Price: ${quoteData.lp} | Change: ${quoteData.ch}`);
                console.log(`Calculated Daily Base Price: ${startingPrice}`);
                await writeToSheet(row, startingPrice);
                
                // Cleanup
                if (typeof quote.delete === 'function') quote.delete();
                else if (typeof quote.close === 'function') quote.close();
                resolve();
            }
        };

        if (typeof quote.onData === 'function') {
            quote.onData(handleData);
        }
        if (typeof quote.on === 'function') {
            quote.on('data', handleData);
        }

        // Fallback in case of a slow/closed market without complete updates
        setTimeout(async () => {
            if (!finished) {
                finished = true;
                console.log(`\n${symbol} TRADINGVIEW QUOTE TIMEOUT`);
                
                let fallback = quoteData.prev_close_price;
                if (quoteData.lp !== undefined && quoteData.ch !== undefined) {
                    fallback = parseFloat((quoteData.lp - quoteData.ch).toFixed(8));
                }

                if (fallback !== undefined && fallback !== null && !isNaN(fallback)) {
                    console.log(`Using Fallback Base Price: ${fallback}`);
                    await writeToSheet(row, fallback);
                } else {
                    console.log(`No valid quote data found for ${symbol}. Market might be fully closed.`);
                }

                if (typeof quote.delete === 'function') quote.delete();
                else if (typeof quote.close === 'function') quote.close();
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
    # Write the script to an isolated temporary file to avoid overriding your existing bot.js
    with open("temp_bot_runner.js", "w") as f:
        f.write(js_code)

    print("Running the Node script...")
    subprocess.run(["node", "temp_bot_runner.js"], check=True)

if __name__ == "__main__":
    main()
