const PriceMonitor = require('./priceMonitor');
const { initializeExchanges } = require('./index');

const TRADING_PAIRS = [
    'BTC/USDT',
    'ETH/USDT',
    'ETH/BTC'
];

async function startMonitoring() {
    const exchanges = initializeExchanges();
    const monitor = new PriceMonitor(exchanges, TRADING_PAIRS);

    process.on('SIGINT', () => {
        monitor.stop();
        process.exit();
    });

    monitor.start().catch(error => {
        logger.error('Monitor failed:', error);
        process.exit(1);
    });
}

startMonitoring();
