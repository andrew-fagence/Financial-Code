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
// PERFECT UK TIMEZONE CALCULATOR
// =====================================================
function getUKDateObj(unixTimestamp) {
    const date = new Date(unixTimestamp * 1000);
    const year = date.getUTCFullYear();

    const march31 = new Date(Date.UTC(year, 2, 31));
    const startBST = new Date(Date.UTC(year, 2, 31 - march31.getUTCDay(), 1));

    const oct31 = new Date(Date.UTC(year, 9, 31));
    const endBST = new Date(Date.UTC(year, 9, 31 - oct31.getUTCDay(), 1));

    const isBST = date >= startBST && date < endBST;
    const offsetHours = isBST ? 1 : 0; 
    return new Date(date.getTime() + offsetHours * 3600 * 1000);
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

        chart.setMarket(symbol, { timeframe: '60' });

        chart.onUpdate(async () => {
            if (finished) return;
            if (!chart.periods || chart.periods.length < 72) return;

            const lastCandle = chart.periods[chart.periods.length - 1];
            const lastUKObj = getUKDateObj(lastCandle.time);
            const targetDateStr = `${lastUKObj.getUTCDate()}/${lastUKObj.getUTCMonth() + 1}/${lastUKObj.getUTCFullYear()}`;

            let exactMidnightPrice = null;
            let firstCandlePrice = null;
            let firstCandleTime = null;

            for (let i = 0; i < chart.periods.length; i++) {
                const candle = chart.periods[i];
                const ukObj = getUKDateObj(candle.time);
                const ukDate = `${ukObj.getUTCDate()}/${ukObj.getUTCMonth() + 1}/${ukObj.getUTCFullYear()}`;
                const ukTime = `${ukObj.getUTCHours().toString().padStart(2, '0')}:${ukObj.getUTCMinutes().toString().padStart(2, '0')}`;

                if (ukDate === targetDateStr) {
                    if (firstCandlePrice === null) {
                        firstCandlePrice = candle.open;
                        firstCandleTime = ukTime;
                    }
                    if (ukTime === '00:00') {
                        exactMidnightPrice = candle.open;
                        break; 
                    }
                }
            }

            finished = true;
            const finalPrice = exactMidnightPrice !== null ? exactMidnightPrice : firstCandlePrice;
            const timeFound = exactMidnightPrice !== null ? '00:00' : firstCandleTime;

            if (finalPrice !== null) {
                console.log(`\n${symbol} UK MIDNIGHT / OPEN`);
                console.log(`Time Found: ${timeFound} UK Time`);
                console.log(`Open Price: ${finalPrice}`);
                await writeToSheet(row, finalPrice);
            } else {
                console.log(`\n${symbol} UK MIDNIGHT`);
                console.log('UK Midnight Price: undefined (No candle found)');
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
