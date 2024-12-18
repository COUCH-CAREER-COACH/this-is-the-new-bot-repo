require('dotenv').config();
const ccxt = require('ccxt');
const winston = require('winston');

const logger = winston.createLogger({
    level: 'info',
    format: winston.format.simple(),
    transports: [new winston.transports.Console()]
});

const exchangeConfig = {
    binance: {
        apiKey: process.env.BINANCE_API_KEY,
        secret: process.env.BINANCE_SECRET,
        fees: {
            taker: parseFloat(process.env.BINANCE_TAKER_FEE) || 0.001
        }
    },
    kraken: {
        apiKey: process.env.KRAKEN_API_KEY,
        secret: process.env.KRAKEN_SECRET,
        fees: {
            taker: parseFloat(process.env.KRAKEN_TAKER_FEE) || 0.0026
        }
    }
};

const mockExchange = {
    fetchBalance: async () => ({
        BTC: { free: 10.0, total: 10.0 },
        USDT: { free: 100000.0, total: 100000.0 },
        ETH: { free: 100.0, total: 100.0 }
    }),
    fetchTicker: async () => ({
        bid: 39900,
        ask: 40000
    })
};

const initializeExchanges = () => {
    try {
        if (process.env.TEST_MODE === 'true') {
            logger.info('Initializing exchanges in test mode');
            return {
                binance: mockExchange,
                kraken: mockExchange
            };
        }
        
        const exchanges = {
            binance: new ccxt.binance(exchangeConfig.binance),
            kraken: new ccxt.kraken(exchangeConfig.kraken)
        };
        return exchanges;
    } catch (error) {
        logger.error('Failed to initialize exchanges:', error);
        throw error;
    }
};

module.exports = { initializeExchanges };
