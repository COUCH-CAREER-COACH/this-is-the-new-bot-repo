module.exports = {
    MINIMUM_PROFIT_PERCENT: 0.5,
    PRICE_UPDATE_INTERVAL: 1000,
    TRADING_PAIRS: [
        'BTC/USDT',
        'ETH/USDT',
        'ETH/BTC'
    ],
    EXCHANGES: {
        BINANCE: {
            RATE_LIMIT: 1200,
            WEIGHT_PER_REQUEST: 1
        },
        KRAKEN: {
            RATE_LIMIT: 1000,
            WEIGHT_PER_REQUEST: 1
        }
    }
};
