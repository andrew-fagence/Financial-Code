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

// Configuration for the newly requested extra data (Cols P & Q)
const extraConfigs = [
    { symbol: 'OANDA:EURUSD', row: 53 },
    { symbol: 'OANDA:GBPUSD', row: 54 },
    { symbol: 'OANDA:EURJPY', row: 55 },
    { symbol: 'OANDA:GBPJPY', row: 56 }
];

// =====================================================
// GOOGLE SHEETS AUTH
// =====================================================
const auth = new google.auth.GoogleAuth({
    keyFile: 'forexdailybias-5ce3a8ede6c9.json',
    scopes: ['https://www.googleapis.com/auth/spreadsheets']
});

const spreadsheetId = '1hsJs7oZY1x3mAQdAfFcQHm3_NDoJT0GepzR8o5tXYlU';

// =====================================================
// WRITE TO SHEET
// =====================================================

async function writeToSheet(row, data) {
    // Explicitly obtain the authenticated client to prevent implicit resolution failures
    const authClient = await auth.getClient();

    const sheets = google.sheets({
        version: 'v4',
        auth: authClient // Pass the resolved client here
    });

    const maxRetries = 10;
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            await sheets.spreadsheets.values.update({
                spreadsheetId,
                range: `Sheet1!B${row}:J${row}`,
                valueInputOption: 'USER_ENTERED',
                requestBody: {
                    values: [[
                        data.pdh,
                        data.pd50,
                        data.pdl,
                        data.pwh,
                        data.pw50,
                        data.pwl,
                        data.dailyTrueOpen,
                        data.asiaHigh,
                        data.asiaLow
                    ]]
                }
            });

            console.log(`Google Sheets updated for row ${row}`);
            return; // Success, exit the loop and function
        } catch (error) {
            if (attempt === maxRetries) {
                console.error(`Failed to update Google Sheets for row ${row} after ${maxRetries} attempts.`, error);
                throw error;
            }
            console.log(`Rate limit or error encountered for row ${row}. Retrying in 5 seconds... (Attempt ${attempt} of ${maxRetries})`);
            await new Promise(resolve => setTimeout(resolve, 5000));
        }
    }
}

async function writeExtraToSheet(row, data) {
    const authClient = await auth.getClient();

    const sheets = google.sheets({
        version: 'v4',
        auth: authClient
    });

    const maxRetries = 10;
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            await sheets.spreadsheets.values.update({
                spreadsheetId,
                range: `Sheet1!P${row}:Q${row}`,
                valueInputOption: 'USER_ENTERED',
                requestBody: {
                    values: [[
                        data.prev1mHigh,
                        data.recent15mClose
                    ]]
                }
            });

            console.log(`Google Sheets updated extra data for row ${row}`);
            return; // Success, exit the loop and function
        } catch (error) {
            if (attempt === maxRetries) {
                console.error(`Failed to update Google Sheets extra data for row ${row} after ${maxRetries} attempts.`, error);
                throw error;
            }
            console.log(`Rate limit or error encountered for extra data row ${row}. Retrying in 5 seconds... (Attempt ${attempt} of ${maxRetries})`);
            await new Promise(resolve => setTimeout(resolve, 5000));
        }
    }
}

// =====================================================
// PROCESS SYMBOL
// =====================================================
async function processSymbol(symbol, row) {
    return new Promise((resolve) => {
        console.log(`\n================================`);
        console.log(`PROCESSING ${symbol}`);
        console.log(`================================`);

        let dailyDone = false;
        let weeklyDone = false;
        let nyDone = false;
        let asiaDone = false;
        let finished = false;

        const data = {
            pdh: null, pdl: null, pd50: null,
            pwh: null, pwl: null, pw50: null,
            dailyTrueOpen: null, asiaHigh: null, asiaLow: null
        };

        async function finish() {
            if (finished) return;

            if (dailyDone && weeklyDone && nyDone && asiaDone) {
                finished = true;
                await writeToSheet(row, data);
                resolve();
            }
        }

        // --- DAILY ---
        const dailyChart = new client.Session.Chart();
        dailyChart.setMarket(symbol, { timeframe: '1D' });
        dailyChart.onUpdate(() => {
            if (!dailyChart.periods || dailyChart.periods.length < 2) return;
            const prev = dailyChart.periods[1];
            data.pdh = prev.max;
            data.pdl = prev.min;
            data.pd50 = (data.pdh + data.pdl) / 2;

            console.log(`\n${symbol} DAILY\nPDH : ${data.pdh}\nPDL : ${data.pdl}\nPD50: ${data.pd50}`);
            dailyDone = true;
            finish();
        });

        // --- WEEKLY ---
        const weeklyChart = new client.Session.Chart();
        weeklyChart.setMarket(symbol, { timeframe: '1W' });
        weeklyChart.onUpdate(() => {
            if (!weeklyChart.periods || weeklyChart.periods.length < 2) return;
            const prev = weeklyChart.periods[1];
            data.pwh = prev.max;
            data.pwl = prev.min;
            data.pw50 = (data.pwh + data.pwl) / 2;

            console.log(`\n${symbol} WEEKLY\nPWH : ${data.pwh}\nPWL : ${data.pwl}\nPW50: ${data.pw50}`);
            weeklyDone = true;
            finish();
        });

        // --- NY MIDNIGHT DTO ---
        const nyChart = new client.Session.Chart();
        nyChart.setMarket(symbol, { timeframe: '60' });
        nyChart.onUpdate(() => {
            if (!nyChart.periods || nyChart.periods.length < 20) return;

            const midnightCandle = nyChart.periods.find(candle => {
                const nyTime = new Date(candle.time * 1000).toLocaleString('en-US', {
                    timeZone: 'America/New_York',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
                return nyTime.includes('24:00') || nyTime.includes('00:00');
            });

            console.log(`\n${symbol} DTO`);
            if (midnightCandle) {
                data.dailyTrueOpen = midnightCandle.open;
                console.log(`NY Open DTO: ${midnightCandle.open}`);
            } else {
                console.log('NY Open DTO: undefined');
            }

            nyDone = true;
            finish();
        });

        // --- ASIA RANGE ---
        const asiaChart = new client.Session.Chart();
        asiaChart.setMarket(symbol, { timeframe: '60' });
        asiaChart.onUpdate(() => {
            if (!asiaChart.periods || asiaChart.periods.length < 30) return;

            const latestDate = new Date(asiaChart.periods[0].time * 1000).toLocaleDateString('en-GB', {
                timeZone: 'Europe/London'
            });

            let asiaHigh = -Infinity;
            let asiaLow = Infinity;

            for (const candle of asiaChart.periods) {
                const date = new Date(candle.time * 1000);
                const candleDate = date.toLocaleDateString('en-GB', { timeZone: 'Europe/London' });
                const candleHour = parseInt(date.toLocaleString('en-GB', {
                    timeZone: 'Europe/London',
                    hour: '2-digit',
                    hour12: false
                }), 10);

                if (candleDate === latestDate && candleHour >= 1 && candleHour <= 5) {
                    asiaHigh = Math.max(asiaHigh, candle.max);
                    asiaLow = Math.min(asiaLow, candle.min);
                }
            }

            data.asiaHigh = asiaHigh;
            data.asiaLow = asiaLow;

            console.log(`\n${symbol} ASIA\nAsia High: ${asiaHigh}\nAsia Low : ${asiaLow}`);
            asiaDone = true;
            finish();
        });
    });
}

// =====================================================
// PROCESS EXTRA SYMBOL (1m High & 15m Close)
// =====================================================
async function processExtraSymbol(symbol, row) {
    return new Promise((resolve) => {
        console.log(`\n================================`);
        console.log(`PROCESSING EXTRA DATA for ${symbol}`);
        console.log(`================================`);

        let done1m = false;
        let done15m = false;
        let finished = false;

        const data = { prev1mHigh: null, recent15mClose: null };

        async function finish() {
            if (finished) return;
            if (done1m && done15m) {
                finished = true;
                await writeExtraToSheet(row, data);
                resolve();
            }
        }

        // --- 1 MINUTE ---
        const chart1m = new client.Session.Chart();
        chart1m.setMarket(symbol, { timeframe: '1' });
        chart1m.onUpdate(() => {
            if (!chart1m.periods || chart1m.periods.length < 2) return;
            // periods[1] represents the previously completed candle
            const prev = chart1m.periods[1];
            data.prev1mHigh = prev.max;

            console.log(`\n${symbol} 1M\nPrev 1m High: ${data.prev1mHigh}`);
            done1m = true;
            finish();
        });

        // --- 15 MINUTE ---
        const chart15m = new client.Session.Chart();
        chart15m.setMarket(symbol, { timeframe: '15' });
        chart15m.onUpdate(() => {
            if (!chart15m.periods || chart15m.periods.length < 2) return;
            // periods[1] represents the most recently completed (closed) candle
            const recent = chart15m.periods[1];
            data.recent15mClose = recent.close;

            console.log(`\n${symbol} 15M\nRecent 15m Close: ${data.recent15mClose}`);
            done15m = true;
            finish();
        });
    });
}

// =====================================================
// MAIN
// =====================================================
(async () => {
    // 1. Process original symbols
    for (const config of configs) {
        await processSymbol(config.symbol, config.row);
    }
    
    // 2. Process newly requested 1m and 15m extra pairs
    for (const config of extraConfigs) {
        await processExtraSymbol(config.symbol, config.row);
    }

    client.end();
    console.log('\nALL SYMBOLS COMPLETE');
})();
