import os
import subprocess
import sys

def main():
    # 1. Retrieve the GCP credentials secret
    gcp_creds = os.environ.get("GCP_CREDENTIALS")
    if not gcp_creds:
        print("Error: GCP_CREDENTIALS environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    # 2. Write the JSON credentials file
    json_filename = "forexdailybias-5ce3a8ede6c9.json"
    try:
        with open(json_filename, "w", encoding="utf-8") as f:
            f.write(gcp_creds)
        print(f"Successfully wrote credentials to {json_filename}")
    except Exception as e:
        print(f"Failed to write credentials file: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Define the JS engine code
    js_code = """const TradingView = require('@mathieuc/tradingview');
const { google } = require('googleapis');

const client = new TradingView.Client();

// =====================================================
// SYMBOLS
// =====================================================

const symbols = [
    'TVC:DXY',
    'FX:JPYBASKET',
    'FX:EURGBP',
    'OANDA:EURUSD',
    'OANDA:GBPUSD',
    'OANDA:EURJPY',
    'OANDA:GBPJPY',
    'TVC:US02Y',
    'TVC:US10Y',
    'CAPITALCOM:US500',
    'CAPITALCOM:US100',
    'CAPITALCOM:GER40',
    'CAPITALCOM:VIX',
    'TVC:USOIL',
    'OANDA:XAUUSD',
    'OANDA:XAGUSD',
    'CRYPTO:BTCUSD'
];

// fixed row mapping (IMPORTANT)
const symbolRows = {
    'TVC:DXY': 88,
    'FX:JPYBASKET': 89,
    'FX:EURGBP': 90,
    'OANDA:EURUSD': 91,
    'OANDA:GBPUSD': 92,
    'OANDA:EURJPY': 93,
    'OANDA:GBPJPY': 94,
    'TVC:US02Y': 95,
    'TVC:US10Y': 96,
    'CAPITALCOM:US500': 97,
    'CAPITALCOM:US100': 98,
    'CAPITALCOM:GER40': 99,
    'CAPITALCOM:VIX': 100,
    'TVC:USOIL': 101,
    'OANDA:XAUUSD': 102,
    'OANDA:XAGUSD': 103,
    'CRYPTO:BTCUSD': 104
};

// =====================================================
// TIMEFRAMES
// =====================================================

const timeframes = {
    M: '1M',
    W: '1W',
    D: '1D',
    H4: '240',
    H1: '60'
};

// =====================================================
// STATE
// =====================================================

let state = {};
let done = {};

for (const s of symbols) {

    state[s] = {
        M: { bull: false, bear: false },
        W: { bull: false, bear: false },
        D: { bull: false, bear: false },
        H4: { bull: false, bear: false },
        H1: { bull: false, bear: false }
    };

    done[s] = {
        M: false,
        W: false,
        D: false,
        H4: false,
        H1: false
    };
}

// =====================================================
// GOOGLE SHEETS
// =====================================================

const auth = new google.auth.GoogleAuth({
    keyFile: 'forexdailybias-5ce3a8ede6c9.json',
    scopes: ['https://www.googleapis.com/auth/spreadsheets']
});

const spreadsheetId = '1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU';

// =====================================================
// FVG ENGINE
// =====================================================

function getActiveFVG(periods) {

    // Sort chronologically (oldest first) based on time to ensure accurate C1, C2, C3 identification
    const sorted = periods.slice().sort((a, b) => a.time - b.time);
    const fvgs = [];

    // FVG requires a 3 candle formation
    for (let k = 1; k < sorted.length - 1; k++) {
        
        const C1 = sorted[k - 1];
        const C2 = sorted[k];
        const C3 = sorted[k + 1];

        // Bullish FVG: C1 High < C3 Low
        if (C1.max < C3.min) {
            fvgs.push({ type: 'BULLISH', gapLow: C1.max, gapHigh: C3.min, c3Index: k + 1, time: C2.time });
        }

        // Bearish FVG: C1 Low > C3 High
        if (C1.min > C3.max) {
            fvgs.push({ type: 'BEARISH', gapHigh: C1.min, gapLow: C3.max, c3Index: k + 1, time: C2.time });
        }
    }

    const active = fvgs.filter(fvg => {

        // Check all candles AFTER C3 to see if the FVG gap was completely filled
        for (let j = fvg.c3Index + 1; j < sorted.length; j++) {
            const candle = sorted[j];

            if (fvg.type === 'BULLISH' && candle.min <= fvg.gapLow) return false;
            if (fvg.type === 'BEARISH' && candle.max >= fvg.gapHigh) return false;
        }

        return true;
    });

    // =====================================================
    // DEBUG OUTPUT (ADDED)
    // =====================================================
    const debug = active.map(f => {

        const date = new Date(f.time * 1000).toLocaleDateString('en-GB', {
            timeZone: 'Europe/London'
        });

        return {
            type: f.type,
            date,
            gapHigh: f.gapHigh,
            gapLow: f.gapLow
        };
    });

    return {
        bull: active.some(f => f.type === 'BULLISH'),
        bear: active.some(f => f.type === 'BEARISH'),
        debug
    };
}

// =====================================================
// FINISH CHECK
// =====================================================

let isFinished = false;

async function finish() {
    if (isFinished) return; // Prevent multiple executions

    for (const s of symbols) {
        for (const tf of Object.keys(timeframes)) {
            if (!done[s][tf]) return;
        }
    }

    isFinished = true; // Lock execution so it only batch updates once
    await writeToSheet();
    client.end();
}

// =====================================================
// SHEET WRITE (ROW-LOCKED TO N:W)
// =====================================================

async function writeToSheet() {

    const sheets = google.sheets({ version: 'v4', auth });

    const data = [];

    for (const s of symbols) {

        const r = [
            state[s].M.bull ? '1M' : '',
            state[s].W.bull ? '1W' : '',
            state[s].D.bull ? '1D' : '',
            state[s].H4.bull ? '4H' : '',
            state[s].H1.bull ? '1H' : '',

            state[s].M.bear ? '1M' : '',
            state[s].W.bear ? '1W' : '',
            state[s].D.bear ? '1D' : '',
            state[s].H4.bear ? '4H' : '',
            state[s].H1.bear ? '1H' : ''
        ];

        data.push({
            range: `Sheet1!N${symbolRows[s]}:W${symbolRows[s]}`,
            values: [r]
        });
    }

    await sheets.spreadsheets.values.batchUpdate({
        spreadsheetId,
        requestBody: {
            valueInputOption: 'USER_ENTERED',
            data
        }
    });

    console.log('Google Sheets updated (DXY + JPY FVG rows)');
}

// =====================================================
// CHART FACTORY
// =====================================================

function createChart(symbol, tfKey, tfValue) {

    const chart = new client.Session.Chart();
    chart.setMarket(symbol, { timeframe: tfValue });

    chart.onUpdate(() => {

        if (!chart.periods || chart.periods.length < 5) return;

        const closed = chart.periods.slice(1); // remove live candle

        const result = getActiveFVG(closed.slice(0, 5));

        state[symbol][tfKey] = result;

        done[symbol][tfKey] = true;

        // =====================================================
        // DEBUG PRINT
        // =====================================================
        if (result.debug && result.debug.length > 0) {
            for (const fvg of result.debug) {
                console.log(
                    `[FVG] ${symbol} ${tfKey} | ${fvg.type} | ${fvg.date} | GH:${fvg.gapHigh} GL:${fvg.gapLow}`
                );
            }
        }

        finish();
    });
}

// =====================================================
// INIT
// =====================================================

for (const symbol of symbols) {
    for (const tfKey of Object.keys(timeframes)) {
        createChart(symbol, tfKey, timeframes[tfKey]);
    }
}
"""

    # 4. Write JS file dynamically
    js_filename = "bot2_engine.js"
    try:
        with open(js_filename, "w", encoding="utf-8") as f:
            f.write(js_code)
        print(f"Successfully generated {js_filename}")
    except Exception as e:
        print(f"Failed to write JS file: {e}", file=sys.stderr)
        sys.exit(1)

    # 5. Run node bot2_engine.js and stream output
    print("Starting bot execution...")
    try:
        process = subprocess.Popen(
            ["node", js_filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())

        rc = process.poll()
        if rc != 0:
            stderr_output = process.stderr.read()
            print(f"Node process exited with code {rc}", file=sys.stderr)
            print(stderr_output, file=sys.stderr)
            sys.exit(rc)
        else:
            print("Bot executed successfully.")

    except Exception as e:
        print(f"Failed to execute node script: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
