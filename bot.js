const TradingView = require('@mathieuc/tradingview');
const fs = require('fs');

console.log("Library imported successfully!");
const client = new TradingView.Client();

const markets = [
    'TVC:DXY', 'FX:JPYBASKET', 'OANDA:EURGBP', 'OANDA:EURUSD', 
    'OANDA:GBPUSD', 'OANDA:EURJPY', 'OANDA:GBPJPY', 'Vantage:SP500', 
    'CAPITALCOM:US100', 'TVC:USOIL', 'OANDA:XAUUSD', 'OANDA:XAGUSD', 
    'CRYPTO:BTCUSD', 'TVC:US02Y', 'TVC:US10Y', 'CBOE:VIX', 'Vantage:GER40'
];

console.log(`Connecting to TradingView to fetch live prices for ${markets.length} markets...`);

const fetchPrice = (symbol) => {
    return new Promise((resolve) => {
        const chart = new client.Session.Chart();
        chart.setMarket(symbol, { timeframe: '1' });
        let isResolved = false;

        const timeout = setTimeout(() => {
            if (!isResolved) {
                isResolved = true;
                resolve({ symbol, price: 'TIMEOUT ERROR' });
            }
        }, 8000);

        chart.onUpdate(() => {
            if (isResolved || !chart.periods[0]) return;
            isResolved = true;
            clearTimeout(timeout);
            resolve({ symbol, price: chart.periods[0].close });
        });

        chart.onError((err) => {
            if (!isResolved) {
                isResolved = true;
                clearTimeout(timeout);
                resolve({ symbol, price: `ERROR: ${err.message || err}` });
            }
        });
    });
};

Promise.all(markets.map(fetchPrice))
    .then((results) => {
        console.log("\n--- Live Market Prices ---");
        results.forEach(res => { console.log(`[${res.symbol}] Last Price: ${res.price}`); });
        fs.writeFileSync('prices.json', JSON.stringify(results, null, 2));
        console.log("\nData successfully saved to prices.json");
    })
    .catch((err) => { console.error("\nUnexpected error during fetch:", err); })
    .finally(() => {
        console.log("Closing connection...");
        client.end();
    });

if (client.onError) {
    client.onError((err) => {
        console.error("Client error:", err);
        client.end();
    });
}
