const { initializeExchanges } = require('./index');

async function testConnections() {
    const exchanges = initializeExchanges();
    
    for (const [name, exchange] of Object.entries(exchanges)) {
        try {
            const ticker = await exchange.fetchTicker('BTC/USDT');
            console.log(`${name} connected successfully:`, ticker);
        } catch (error) {
            console.error(`${name} connection failed:`, error.message);
        }
    }
}

testConnections();
