
const winston = require('winston');
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.json(),
    transports: [
        new winston.transports.File({ filename: 'price-monitor.log' }),
        new winston.transports.Console()
    ]
});

class PriceMonitor {
    constructor(exchanges, pairs) {
        this.exchanges = exchanges;
        this.pairs = pairs;
        this.prices = new Map();
        this.updateInterval = 1000; // 1 second
        this.running = false;
    }

    async start() {
        this.running = true;
        while(this.running) {
            await this.updatePrices();
            await new Promise(resolve => setTimeout(resolve, this.updateInterval));
        }
    }

    async updatePrices() {
        for (const pair of this.pairs) {
            for (const [exchangeName, exchange] of Object.entries(this.exchanges)) {
                try {
                    const ticker = await exchange.fetchTicker(pair);
                    this.prices.set(`${exchangeName}-${pair}`, {
                        bid: ticker.bid,
                        ask: ticker.ask,
                        timestamp: Date.now()
                    });
                    logger.debug(`Updated ${exchangeName} ${pair}: ${ticker.bid}/${ticker.ask}`);
                } catch (error) {
                    logger.error(`Error fetching ${pair} price from ${exchangeName}: ${error.message}`);
                }
            }
        }
    }

    findArbitrageOpportunities(minProfitPercent = 0.5) {
        const opportunities = [];
        
        for (const pair of this.pairs) {
            const exchangePrices = Array.from(this.prices.entries())
                .filter(([key]) => key.endsWith(pair))
                .map(([key, value]) => ({
                    exchange: key.split('-')[0],
                    ...value
                }));

            for (let i = 0; i < exchangePrices.length; i++) {
                for (let j = i + 1; j < exchangePrices.length; j++) {
                    const buyExchange = exchangePrices[i];
                    const sellExchange = exchangePrices[j];

                    const profit = ((sellExchange.bid - buyExchange.ask) / buyExchange.ask) * 100;
                    
                    if (profit > minProfitPercent) {
                        opportunities.push({
                            pair,
                            buyExchange: buyExchange.exchange,
                            sellExchange: sellExchange.exchange,
                            buyPrice: buyExchange.ask,
                            sellPrice: sellExchange.bid,
                            profitPercent: profit
                        });
                    }
                }
            }
        }
        
        return opportunities;
    }

    stop() {
        this.running = false;
    }
}

module.exports = PriceMonitor;
