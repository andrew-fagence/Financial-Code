import subprocess
import os

def run_command(command):
    subprocess.run(command, shell=True, check=True)

# Blocks 1, 4, 7, 10: Install dependencies
print("Installing npm dependencies...")
run_command("npm install @mathieuc/tradingview")
run_command("npm install googleapis")

# Using a temporary filename so we don't overwrite your existing bot.js in the repo
js_filename = "temp_bond_bot.js"

# ==========================================
# Unified Batch Execution for US, EU, GB, JP Markets
# ==========================================
js_code = r"""const TradingView = require('@mathieuc/tradingview');
const { google } = require('googleapis');

console.log("Libraries imported successfully!");

const client = new TradingView.Client();

const marketsUS = [
    'TVC:US03M', 'TVC:US06M', 'TVC:US01Y', 'TVC:US02Y', 'TVC:US03Y',
    'TVC:US05Y', 'TVC:US07Y', 'TVC:US10Y', 'TVC:US20Y', 'TVC:US30Y'
];

const marketsEU = [
    'TVC:EU03MY', 'TVC:EU06MY', 'TVC:EU01Y', 'TVC:EU02Y', 'TVC:EU03Y',
    'TVC:EU05Y', 'TVC:EU07Y', 'TVC:EU10Y', 'TVC:EU20Y', 'TVC:EU30Y'
];

const marketsGB = [
    'TVC:GB03MY', 'TVC:GB06MY', 'TVC:GB01Y', 'TVC:GB02Y', 'TVC:GB03Y',
    'TVC:GB05Y', 'TVC:GB07Y', 'TVC:GB10Y', 'TVC:GB20Y', 'TVC:GB30Y'
];

const marketsJP = [
    'TVC:JP03MY', 'TVC:JP06MY', 'TVC:JP01Y', 'TVC:JP02Y', 'TVC:JP03Y',
    'TVC:JP05Y', 'TVC:JP07Y', 'TVC:JP10Y', 'TVC:JP20Y', 'TVC:JP30Y'
];

const columns = [
    'B','C','D','E','F',
    'G','H','I','J','K'
];

const spreadsheetId = '1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU';

const fs = require('fs');

console.log("Node working directory:", process.cwd());
console.log(
    "JSON exists:",
    fs.existsSync('forexdailybias-5ce3a8ede9c2.json')
);

const keyData = require('./forexdailybias-5ce3a8ede9c2.json');
if (keyData.private_key) {
    keyData.private_key = keyData.private_key.replace(/\\n/g, '\n');
}

const auth = new google.auth.GoogleAuth({
    credentials: keyData,
    scopes: ['https://www.googleapis.com/auth/spreadsheets']
});

const fetchPrice = (symbol) => {
    return new Promise((resolve) => {

        const chart = new client.Session.Chart();

        chart.setMarket(symbol, {
            timeframe: '1'
        });

        let done = false;

        const timeout = setTimeout(() => {
            if (!done) {
                done = true;
                resolve({
                    symbol,
                    price: null
                });
            }
        }, 8000);

        chart.onUpdate(() => {

            if (done || !chart.periods?.[0]) return;

            done = true;
            clearTimeout(timeout);

            resolve({
                symbol,
                price: chart.periods[0].close
            });
        });

        chart.onError((err) => {

            if (done) return;

            done = true;
            clearTimeout(timeout);

            console.error(
                `TradingView error for ${symbol}:`,
                err
            );

            resolve({
                symbol,
                price: null
            });
        });
    });
};

async function writeToGoogleSheetsBatch(resultsUS, resultsEU, resultsGB, resultsJP) {

    const authClient = await auth.getClient();

    const sheets = google.sheets({
        version: 'v4',
        auth: authClient
    });

    const toValues = (results) => results.map(r => r.price === null ? '' : r.price);
    
    // Combining everything into a 2D array, natively supported by sheets for batching rows
    const values = [
        toValues(resultsUS), // Updates Row 146
        toValues(resultsEU), // Updates Row 147
        toValues(resultsGB), // Updates Row 148
        toValues(resultsJP)  // Updates Row 149
    ];

    let attempt = 0;
    const maxRetries = 10;

    while (attempt < maxRetries) {
        try {
            await sheets.spreadsheets.values.update({
                spreadsheetId,
                range: 'Sheet1!B146:K149',
                valueInputOption: 'USER_ENTERED',
                requestBody: {
                    values: values
                }
            });

            console.log("\nGoogle Sheets updated (1 Single Batch API Call):");
            console.log("Sheet1!B146:K149");
            console.log(values);
            break; // Break the loop on success
        } catch (err) {
            attempt++;
            console.error(`\nError updating Google Sheets (Attempt ${attempt} of ${maxRetries}):`, err.message || err);
            
            if (attempt >= maxRetries) {
                throw err; // Re-throw error if max retries met
            }
            
            // Wait increasingly longer (10s, 20s, 30s...) before retrying
            const waitMs = attempt * 10000;
            console.log(`Waiting ${waitMs / 1000} seconds before retrying...`);
            await new Promise(resolve => setTimeout(resolve, waitMs));
        }
    }
}

(async () => {

    try {
        console.log(`Fetching live yields for US Markets...`);
        const resultsUS = await Promise.all(marketsUS.map(fetchPrice));
        
        console.log(`Fetching live yields for EU Markets...`);
        const resultsEU = await Promise.all(marketsEU.map(fetchPrice));
        
        console.log(`Fetching live yields for GB Markets...`);
        const resultsGB = await Promise.all(marketsGB.map(fetchPrice));
        
        console.log(`Fetching live yields for JP Markets...`);
        const resultsJP = await Promise.all(marketsJP.map(fetchPrice));

        console.log("\n--- Live Market Prices ---");
        const allResults = [...resultsUS, ...resultsEU, ...resultsGB, ...resultsJP];
        allResults.forEach((res, i) => {
            console.log(`${res.symbol} = ${res.price}`);
        });

        await writeToGoogleSheetsBatch(resultsUS, resultsEU, resultsGB, resultsJP);

    } catch (err) {

        console.error(
            "\nUnexpected error:",
            err
        );

    } finally {

        client.end();
        console.log("\nConnection closed.");
    }
})();
"""
with open(js_filename, "w") as f:
    f.write(js_code)

print(f"\nRunning All Markets Script...")
run_command(f"node {js_filename}")

# Clean up the temporary JavaScript file
if os.path.exists(js_filename):
    os.remove(js_filename)
    print(f"\nTemporary file '{js_filename}' cleaned up.")
