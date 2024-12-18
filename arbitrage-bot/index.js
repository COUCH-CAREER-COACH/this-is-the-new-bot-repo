require('dotenv').config();
const axios = require('axios');
const ccxt = require('ccxt');
const winston = require('winston');

// Configure logger
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.printf(({ level, message, timestamp, ...rest }) => {
            const testMode = process.env.TEST_MODE === 'true' ? '[TEST MODE] ' : '';
            return JSON.stringify({
                timestamp,
                level,
                message: `${testMode}${message}`,
                ...rest
            });
        })
    ),
    transports: [
        new winston.transports.File({ filename: 'error.log', level: 'error' }),
        new winston.transports.File({ filename: 'combined.log' }),
        new winston.transports.Console()
    ]
});

// Exchange configuration
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

// Validate configuration
function validateConfig() {
    // Test mode check
    const isTestMode = process.env.TEST_MODE === 'true';
    const isBinanceUS = process.env.BINANCE_US_MODE === 'true';
    const requiredEnvVars = [
        'TRADING_PAIR',
        'TRADING_AMOUNT',
        'MIN_PROFIT_PERCENT'
    ];
    
    if (!isTestMode) {
        requiredEnvVars.push(
            'BINANCE_API_KEY',
            'BINANCE_SECRET',
            'KRAKEN_API_KEY',
            'KRAKEN_SECRET'
        );
    }

    for (const envVar of requiredEnvVars) {
        if (!process.env[envVar]) {
            throw new Error(`Missing required environment variable: ${envVar}`);
        }
    }
    
    if (isNaN(parseFloat(process.env.TRADING_AMOUNT)) || parseFloat(process.env.TRADING_AMOUNT) <= 0) {
        throw new Error('Invalid TRADING_AMOUNT');
    }
    
    if (isNaN(parseFloat(process.env.MIN_PROFIT_PERCENT)) || parseFloat(process.env.MIN_PROFIT_PERCENT) < 0) {
        throw new Error('Invalid MIN_PROFIT_PERCENT');
    }
}

// Check IP location before API requests
async function checkIPLocation() {
    try {
        const response = await axios.get('https://ipapi.co/json/');
        const country = response.data.country;
        if (country === 'US' && process.env.BINANCE_US_MODE !== 'true') {
            throw new Error('Binance API is restricted in your location. Please enable BINANCE_US_MODE.');
        }
    } catch (error) {
        logger.error('Failed to check IP location:', error);
        throw error;
    }
}
async function withBackoff(fn, maxRetries = 5, stopOnLocationError = false) {
    let retries = 0;
    while (true) {
        try {
            return await fn();
        } catch (error) {
            if (error.name === 'ExchangeNotAvailable' && 
                error.message.includes('Service unavailable from a restricted location')) {
                    logger.error('Binance service is restricted in your location. Stopping further attempts.');
                    if (stopOnLocationError) {
                        process.exit(1);
                    }
                logger.error('Binance service is restricted in your location. Consider setting BINANCE_US_MODE=true if you are in the US.');
                throw error;
            }
            if (error.name === 'RateLimitExceeded' && retries < maxRetries) {
                retries++;
                const delay = Math.min(1000 * Math.pow(2, retries), 30000);
                logger.warn(`Rate limit hit, backing off for ${delay}ms`);
                await new Promise(resolve => setTimeout(resolve, delay));
            } else {
                throw error;
            }
        }
    }
}

// Initialize exchanges
const mockExchange = {
    fetchBalance: async () => ({
        BTC: { free: 10.0, total: 10.0 },
        USDT: { free: 100000.0, total: 100000.0 },
        ETH: { free: 100.0, total: 100.0 }
    }),
    fetchOrderBook: async () => ({
        asks: [[40000, 1.0], [40100, 2.0]],
        bids: [[39900, 1.0], [39800, 2.0]]
    }),
    fetchTicker: async () => ({
        bid: 39900,
        ask: 40000
    }),
    fees: { taker: 0.001 }
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
        
        const binanceClass = process.env.BINANCE_US_MODE === 'true' ? ccxt.binanceus : ccxt.binance;
        const exchanges = {
            binance: new binanceClass(exchangeConfig.binance),
            kraken: new ccxt.kraken(exchangeConfig.kraken)
        };
        return exchanges;
    } catch (error) {
        logger.error('Failed to initialize exchanges:', error);
        throw error;
    }
};

// Fetch prices from an exchange
async function checkBalance(exchange, symbol, amount) {
    try {
        const balance = await withBackoff(() => exchange.fetchBalance());
        const [base, quote] = symbol.split('/');
        
        if (!balance[base] || !balance[quote]) {
            throw new Error(`Missing balance for ${base} or ${quote}`);
        }
        
        if (balance[base].free < amount) {
            throw new Error(`Insufficient ${base} balance: ${balance[base].free} < ${amount}`);
        }
        
        return true;
    } catch (error) {
        logger.error(`Error checking balance: ${error.message}`);
        throw error;
    }
}

async function analyzeOrderBook(exchange, symbol, amount, side) {
    try {
        const orderBook = await withBackoff(() => exchange.fetchOrderBook(symbol, 20));
        const orders = side === 'buy' ? orderBook.asks : orderBook.bids;
        let availableVolume = 0;
        let averagePrice = 0;
        let totalCost = 0;
        
        for (const [price, volume] of orders) {
            const orderVolume = Math.min(amount - availableVolume, volume);
            availableVolume += orderVolume;
            totalCost += orderVolume * price;
            
            if (availableVolume >= amount) {
                averagePrice = totalCost / amount;
                return { hasLiquidity: true, price: averagePrice };
            }
        }
        
        return { hasLiquidity: false, price: 0 };
    } catch (error) {
        logger.error(`Error analyzing order book: ${error.message}`);
        throw error;
    }
}

async function fetchPrice(exchange, symbol) {
    try {
        const ticker = await withBackoff(() => exchange.fetchTicker(symbol));
        return {
            bid: ticker.bid,
            ask: ticker.ask
        };
    } catch (error) {
        logger.error(`Error fetching price for ${symbol}:`, error);
        throw error;
    }
}

// Calculate arbitrage opportunity
function calculateArbitrage(buyExchange, sellExchange, buyPrice, sellPrice, tradingAmount) {
    // Calculate fees
    const buyFee = buyExchange.fees.taker * tradingAmount * buyPrice;
    const sellFee = sellExchange.fees.taker * tradingAmount * sellPrice;
    
    // Calculate gross and net profit
    const grossProfit = (sellPrice - buyPrice) * tradingAmount;
    const netProfit = grossProfit - buyFee - sellFee;
    const profitPercentage = (netProfit / (buyPrice * tradingAmount)) * 100;
    
    return {
        grossProfit,
        netProfit,
        profitPercentage,
        fees: {
            buy: buyFee,
            sell: sellFee,
            total: buyFee + sellFee
        }
    };
}

// Main arbitrage loop
async function main() {
    try {
        logger.info('Starting arbitrage bot...');
        validateConfig();
        
        await checkIPLocation();
        const exchanges = initializeExchanges();
        const symbol = process.env.TRADING_PAIR;
        const tradingAmount = parseFloat(process.env.TRADING_AMOUNT);
        const minProfitPercent = parseFloat(process.env.MIN_PROFIT_PERCENT);

        while (true) {
            try {
                // Check balances
                await checkBalance(exchanges.binance, symbol, tradingAmount);
                await checkBalance(exchanges.kraken, symbol, tradingAmount);
                
                // Analyze order books for both exchanges
                const binanceLiquidity = await analyzeOrderBook(exchanges.binance, symbol, tradingAmount, 'buy');
                const krakenLiquidity = await analyzeOrderBook(exchanges.kraken, symbol, tradingAmount, 'buy');
                
                if (!binanceLiquidity.hasLiquidity || !krakenLiquidity.hasLiquidity) {
                    logger.warn('Insufficient liquidity in order books');
                    continue;
                }
                
                const binancePrice = await fetchPrice(exchanges.binance, symbol);
                const krakenPrice = await fetchPrice(exchanges.kraken, symbol);

                const arbitrage1 = calculateArbitrage(
                    exchanges.binance,
                    exchanges.kraken,
                    binancePrice.ask,
                    krakenPrice.bid,
                    tradingAmount
                );

                const arbitrage2 = calculateArbitrage(
                    exchanges.kraken,
                    exchanges.binance,
                    krakenPrice.ask,
                    binancePrice.bid,
                    tradingAmount
                );

                // Log opportunities if they exceed minimum profit threshold
                if (arbitrage1.profitPercentage > minProfitPercent) {
                    if (process.env.TEST_MODE === 'true') {
                        // Simulate trade execution in test mode
                        logger.info('Simulating trade execution:', {
                            direction: 'Binance -> Kraken',
                            ...arbitrage1,
                            simulation: {
                                buyPrice: binancePrice.ask,
                                sellPrice: krakenPrice.bid,
                                amount: tradingAmount
                            }
                        });
                    } else {
                        logger.info('Arbitrage opportunity found:', {
                            direction: 'Binance -> Kraken',
                            ...arbitrage1
                        });
                    }
                }

                if (arbitrage2.profitPercentage > minProfitPercent) {
                    if (process.env.TEST_MODE === 'true') {
                        // Simulate trade execution in test mode
                        logger.info('Simulating trade execution:', {
                            direction: 'Kraken -> Binance',
                            ...arbitrage2,
                            simulation: {
                                buyPrice: krakenPrice.ask,
                                sellPrice: binancePrice.bid,
                                amount: tradingAmount
                            }
                        });
                    } else {
                        logger.info('Arbitrage opportunity found:', {
                            direction: 'Kraken -> Binance',
                            ...arbitrage2
                        });
                    }
                }

                // Add delay to avoid rate limits
                await new Promise(resolve => setTimeout(resolve, 3000));
            } catch (error) {
                logger.error('Error in main loop:', error);
                // Wait before retrying on error
                await new Promise(resolve => setTimeout(resolve, 5000));
            }
        }
    } catch (error) {
        logger.error('Fatal error in main function:', error);
        process.exit(1);
    }
}

// Start the bot
main().catch(error => {
    logger.error('Unhandled error:', error);
    process.exit(1);
});
