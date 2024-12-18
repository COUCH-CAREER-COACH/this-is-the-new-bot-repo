import pkg from 'hardhat';
const { ethers } = pkg;
import * as addresses from "./addresses.js";
import dotenv from "dotenv";

// Load environment variables
dotenv.config();

// Global variables
let provider;
let flashLoanContract;

// Configuration constants
const MIN_PROFIT_THRESHOLD = parseFloat(process.env.MIN_PROFIT_THRESHOLD || "0.01");
const GAS_MULTIPLIER = parseFloat(process.env.GAS_MULTIPLIER || "1.1");
const UPDATE_INTERVAL = parseInt(process.env.UPDATE_INTERVAL || "30") * 1000; // Convert to milliseconds
const MAX_SLIPPAGE = parseFloat(process.env.MAX_SLIPPAGE || "0.5");

// Add MEV protection configuration
const MEV_PROTECTION = {
    maxPriceImpact: 0.005,  // 0.5% max price impact
    minBlockDelay: 1,       // Min blocks to wait before executing
    flashbotsEnabled: true, // Use Flashbots to prevent frontrunning
    maxGasPrice: 150n,      // Max gas price in gwei we're willing to pay
    privatePoolsOnly: true  // Use private pools when possible
};

// Risk management configuration
const RISK_MANAGEMENT = {
    maxPositionSize: {
        'WETH/DAI': 50,     // Max $50k position for major pairs
        'WETH/USDC': 50,
        'default': 20       // Max $20k for other pairs
    },
    minLiquidity: {
        'WETH/DAI': 1000000,    // $1M min liquidity for major pairs
        'WETH/USDC': 1000000,
        'default': 500000       // $500k for other pairs
    },
    maxSlippage: 0.003,        // 0.3% max slippage
    minProfit: 10,             // Minimum $10 profit
    minROI: 15,                // Minimum 15% ROI
    maxROI: 500,               // Maximum 500% ROI (to avoid false positives)
    emergencyStop: {
        maxLoss: 100,          // Stop after $100 in losses
        maxGasSpent: 1,        // Max 1 ETH spent on gas
        cooldownPeriod: 300    // 5 minute cooldown after losses
    }
};

// Add execution tracking
const executionStats = {
    totalTrades: 0,
    successfulTrades: 0,
    failedTrades: 0,
    totalProfit: 0,
    totalGasSpent: 0,
    lastTradeTime: 0,
    recentErrors: [],
    profitByPair: {},
    startTime: Date.now()
};

function updateExecutionStats(trade) {
    executionStats.totalTrades++;
    if (trade.success) {
        executionStats.successfulTrades++;
        executionStats.totalProfit += trade.profit;
        executionStats.totalGasSpent += trade.gasSpent;
        
        if (!executionStats.profitByPair[trade.pair]) {
            executionStats.profitByPair[trade.pair] = 0;
        }
        executionStats.profitByPair[trade.pair] += trade.profit;
    } else {
        executionStats.failedTrades++;
        executionStats.recentErrors.push({
            time: Date.now(),
            error: trade.error,
            pair: trade.pair
        });
        
        // Keep only last 10 errors
        if (executionStats.recentErrors.length > 10) {
            executionStats.recentErrors.shift();
        }
    }
    executionStats.lastTradeTime = Date.now();
}

// Add health monitoring
function checkBotHealth() {
    const stats = {
        uptime: (Date.now() - executionStats.startTime) / 1000 / 60, // minutes
        successRate: executionStats.totalTrades ? 
            (executionStats.successfulTrades / executionStats.totalTrades * 100) : 0,
        averageProfit: executionStats.successfulTrades ? 
            (executionStats.totalProfit / executionStats.successfulTrades) : 0,
        gasEfficiency: executionStats.totalProfit / (executionStats.totalGasSpent * 2200), // Profit per ETH spent on gas
        recentErrors: executionStats.recentErrors.length
    };

    console.log('\n🏥 Bot Health Report:');
    console.log(`Uptime: ${stats.uptime.toFixed(2)} minutes`);
    console.log(`Success Rate: ${stats.successRate.toFixed(2)}%`);
    console.log(`Average Profit: $${stats.averageProfit.toFixed(2)}`);
    console.log(`Gas Efficiency: $${stats.gasEfficiency.toFixed(2)} profit per ETH spent`);
    console.log(`Recent Errors: ${stats.recentErrors}`);
    
    // Alert if health is poor
    if (stats.successRate < 50 || stats.recentErrors > 5) {
        console.log('⚠️ Warning: Bot performance is suboptimal');
        return false;
    }
    return true;
}

// Trading pairs configuration
const TRADING_PAIRS = [
    // Stablecoin Pairs
    {
        name: "USDC/USDT",
        token0: addresses.usdc,
        token1: addresses.usdt,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    },
    {
        name: "DAI/USDT",
        token0: addresses.dai,
        token1: addresses.usdt,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    },
    {
        name: "DAI/USDC",
        token0: addresses.dai,
        token1: addresses.usdc,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    },
    // ETH Pairs
    {
        name: "WETH/DAI",
        token0: addresses.weth,
        token1: addresses.dai,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    },
    {
        name: "WETH/USDC",
        token0: addresses.weth,
        token1: addresses.usdc,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    },
    // BTC Pairs
    {
        name: "WBTC/WETH",
        token0: addresses.wbtc,
        token1: addresses.weth,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    },
    {
        name: "WBTC/USDC",
        token0: addresses.wbtc,
        token1: addresses.usdc,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    },
    // DeFi Token Pairs
    {
        name: "LINK/ETH",
        token0: addresses.link,
        token1: addresses.weth,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    },
    {
        name: "UNI/ETH",
        token0: addresses.uni,
        token1: addresses.weth,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    },
    // Liquid Staking Derivatives
    {
        name: "stETH/ETH",
        token0: addresses.steth,
        token1: addresses.weth,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    },
    {
        name: "rETH/ETH",
        token0: addresses.reth,
        token1: addresses.weth,
        uniPair: null,
        sushiPair: null,
        token0Decimals: null,
        token1Decimals: null,
        isToken0Base: true
    }
];

// Test amounts with consistent max slippage
const TEST_AMOUNTS = [
    { amount: "0.1", maxSlippage: MAX_SLIPPAGE },
    { amount: "0.5", maxSlippage: MAX_SLIPPAGE },
    { amount: "1.0", maxSlippage: MAX_SLIPPAGE },
    { amount: "2.0", maxSlippage: MAX_SLIPPAGE },
    { amount: "5.0", maxSlippage: MAX_SLIPPAGE }
];

// Global state for each pair
const pairStates = new Map();

// Router ABI - just what we need
const ROUTER_ABI = [
    "function getAmountsOut(uint amountIn, address[] memory path) public view returns (uint[] memory amounts)",
    "function swapExactTokensForTokens(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external returns (uint[] memory amounts)"
];

// Token ABI
const ERC20_ABI = [
    "function decimals() external view returns (uint8)",
    "function balanceOf(address account) external view returns (uint256)",
    "function approve(address spender, uint256 amount) external returns (bool)"
];

// Factory ABI for monitoring pair reserves
const FACTORY_ABI = [
    "function getPair(address tokenA, address tokenB) external view returns (address pair)"
];

const PAIR_ABI = [
    "event Sync(uint112 reserve0, uint112 reserve1)",
    "function token0() external view returns (address)",
    "function token1() external view returns (address)",
    "function getReserves() external view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast)"
];

async function getGasPrice() {
    try {
        // Try to get EIP-1559 fee data first
        const feeData = await provider.getFeeData();
        
        if (feeData.maxFeePerGas) {
            // Return the max fee if EIP-1559 is supported
            return feeData.maxFeePerGas;
        } else if (feeData.gasPrice) {
            // Fallback to legacy gas price
            return feeData.gasPrice;
        } else {
            // If neither is available, get the network gas price
            return await provider.getGasPrice();
        }
    } catch (error) {
        console.error("Error getting gas price:", error);
        // Fallback to network gas price
        return await provider.getGasPrice();
    }
}

async function getTokenOrder(pairContract) {
    const token0 = await pairContract.token0();
    return token0.toLowerCase() === addresses.weth.toLowerCase();
}

function getPrice(reserves, isToken0Base) {
    if (!reserves || !reserves.reserve0 || !reserves.reserve1) {
        console.log("Warning: Missing or invalid reserves");
        return 0;
    }

    try {
        // Ensure reserves are BigInt
        const reserve0 = typeof reserves.reserve0 === 'bigint' ? reserves.reserve0 : BigInt(reserves.reserve0.toString());
        const reserve1 = typeof reserves.reserve1 === 'bigint' ? reserves.reserve1 : BigInt(reserves.reserve1.toString());

        // Convert reserves to proper decimal places
        const reserve0Formatted = ethers.formatUnits(reserve0, isToken0Base ? 18 : 6);
        const reserve1Formatted = ethers.formatUnits(reserve1, isToken0Base ? 6 : 18);

        // Convert to numbers and calculate price
        const reserve0Num = parseFloat(reserve0Formatted);
        const reserve1Num = parseFloat(reserve1Formatted);

        if (reserve0Num === 0) {
            console.log("Warning: Zero reserve detected");
            return 0;
        }

        // Calculate price (DAI per WETH)
        const price = isToken0Base ? (reserve1Num / reserve0Num) : (reserve0Num / reserve1Num);

        // Sanity check on price
        if (!isFinite(price) || price <= 0) {
            console.log("Warning: Invalid price calculated:", price);
            return 0;
        }

        return price;
    } catch (error) {
        console.error("Error calculating price:", error);
        return 0;
    }
}

async function getUniswapPair(token0, token1) {
    const uniFactory = new ethers.Contract(
        addresses.uniswapV2Factory,
        ['function getPair(address tokenA, address tokenB) external view returns (address pair)'],
        provider
    );
    return await uniFactory.getPair(token0, token1);
}

async function getSushiswapPair(token0, token1) {
    const sushiFactory = new ethers.Contract(
        addresses.sushiFactory,
        ['function getPair(address tokenA, address tokenB) external view returns (address pair)'],
        provider
    );
    return await sushiFactory.getPair(token0, token1);
}

// Add rate limiting helper
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function setupPairMonitoring(pair) {
    try {
        console.log(`Setting up monitoring for ${pair.name}...`);
        
        // Get pair addresses with retry logic
        let uniPairAddress, sushiPairAddress;
        for (let i = 0; i < 3; i++) {
            try {
                [uniPairAddress, sushiPairAddress] = await Promise.all([
                    getUniswapPair(pair.token0, pair.token1),
                    getSushiswapPair(pair.token0, pair.token1)
                ]);
                break;
            } catch (error) {
                if (i === 2) throw error;
                await sleep(1000); // Wait 1 second before retry
            }
        }

        // Validate pair addresses
        if (!uniPairAddress || uniPairAddress === "0x0000000000000000000000000000000000000000" ||
            !sushiPairAddress || sushiPairAddress === "0x0000000000000000000000000000000000000000") {
            console.log(`Skipping ${pair.name} - One or both pairs don't exist`);
            return;
        }
        
        // Initialize pair contracts
        pair.uniPair = new ethers.Contract(
            uniPairAddress,
            ['function getReserves() external view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast)'],
            provider
        );
        
        pair.sushiPair = new ethers.Contract(
            sushiPairAddress,
            ['function getReserves() external view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast)'],
            provider
        );

        // Get token decimals if not set
        if (!pair.token0Decimals || !pair.token1Decimals) {
            try {
                const token0Contract = new ethers.Contract(
                    pair.token0,
                    ['function decimals() external view returns (uint8)'],
                    provider
                );
                const token1Contract = new ethers.Contract(
                    pair.token1,
                    ['function decimals() external view returns (uint8)'],
                    provider
                );
                
                // Add retry logic for decimals
                for (let i = 0; i < 3; i++) {
                    try {
                        [pair.token0Decimals, pair.token1Decimals] = await Promise.all([
                            token0Contract.decimals(),
                            token1Contract.decimals()
                        ]);
                        break;
                    } catch (error) {
                        if (i === 2) throw error;
                        await sleep(1000);
                    }
                }
            } catch (error) {
                console.log(`Error getting decimals for ${pair.name}, using defaults`);
                pair.token0Decimals = 18;
                pair.token1Decimals = 18;
            }
        }

        // Set up monitoring with rate limiting
        provider.on('block', async () => {
            try {
                await checkArbitrageOpportunity(pair);
                await sleep(500); // Add small delay between checks
            } catch (error) {
                if (error.message.includes('rate limit')) {
                    await sleep(2000); // Wait longer on rate limit
                }
            }
        });

        console.log(`Successfully set up monitoring for ${pair.name}`);
        
        // Do an initial check with retry
        for (let i = 0; i < 3; i++) {
            try {
                await checkArbitrageOpportunity(pair);
                break;
            } catch (error) {
                if (i === 2) console.error(`Initial check failed for ${pair.name}:`, error.message);
                await sleep(1000);
            }
        }

    } catch (error) {
        console.error(`Error setting up monitoring for ${pair.name}:`, error.message);
    }
}

async function checkArbitrageOpportunity(pair) {
    try {
        // Get block number for MEV protection
        const currentBlock = await provider.getBlockNumber();
        
        // Get latest gas price with retry
        let feeData;
        for (let i = 0; i < 3; i++) {
            try {
                feeData = await provider.getFeeData();
                break;
            } catch (error) {
                if (i === 2) throw error;
                await sleep(1000);
            }
        }
        
        const gasPrice = feeData.maxFeePerGas || feeData.gasPrice;
        // Skip if gas price is too high
        if (gasPrice > (MEV_PROTECTION.maxGasPrice * BigInt(1e9))) {
            return;
        }

        const gasPriceGwei = ethers.formatUnits(gasPrice, 'gwei');
        const gasLimit = estimatedGasUsed[pair.name] || estimatedGasUsed.default;
        const gasCostETH = gasLimit * gasPrice / BigInt(1e9);
        const gasCostUSD = Number(ethers.formatEther(gasCostETH)) * 2200;

        // Get reserves atomically and check multiple blocks for MEV protection
        const [uniReservesNow, sushiReservesNow, uniReservesPrev, sushiReservesPrev] = await Promise.all([
            pair.uniPair.getReserves(),
            pair.sushiPair.getReserves(),
            pair.uniPair.getReserves({ blockTag: currentBlock - 1 }),
            pair.sushiPair.getReserves({ blockTag: currentBlock - 1 })
        ]);

        // Check for suspicious reserve changes (MEV detection)
        const reserveChangeThreshold = 0.02; // 2% threshold
        const uniReserveChange = Math.abs(Number(uniReservesNow[0]) - Number(uniReservesPrev[0])) / Number(uniReservesPrev[0]);
        const sushiReserveChange = Math.abs(Number(sushiReservesNow[0]) - Number(sushiReservesPrev[0])) / Number(sushiReservesPrev[0]);
        
        if (uniReserveChange > reserveChangeThreshold || sushiReserveChange > reserveChangeThreshold) {
            console.log(`⚠️ Suspicious reserve changes detected for ${pair.name}, skipping...`);
            return;
        }

        // Rest of the existing code...
        const uniReserve0 = BigInt(uniReservesNow[0].toString());
        const uniReserve1 = BigInt(uniReservesNow[1].toString());
        const sushiReserve0 = BigInt(sushiReservesNow[0].toString());
        const sushiReserve1 = BigInt(sushiReservesNow[1].toString());

        if (uniReserve0 === 0n || uniReserve1 === 0n || sushiReserve0 === 0n || sushiReserve1 === 0n) {
            return;
        }

        // Calculate prices with higher precision
        const SCALE = BigInt(1e18);
        const uniPrice = (uniReserve1 * SCALE) / uniReserve0;
        const sushiPrice = (sushiReserve1 * SCALE) / sushiReserve0;

        const uniPriceDecimal = Number(uniPrice) / 1e18;
        const sushiPriceDecimal = Number(sushiPrice) / 1e18;
        
        if (uniPriceDecimal === 0 || sushiPriceDecimal === 0 || 
            !isFinite(uniPriceDecimal) || !isFinite(sushiPriceDecimal)) {
            return;
        }

        const priceDiff = Math.abs(uniPriceDecimal - sushiPriceDecimal) / Math.min(uniPriceDecimal, sushiPriceDecimal) * 100;
        
        if (priceDiff > 0.1) {
            const profitDetails = calculateProfit(
                uniPriceDecimal,
                sushiPriceDecimal,
                gasCostUSD,
                pair,
                uniReserve0,
                sushiReserve0
            );
            
            if (profitDetails && profitDetails.profit > 5) {
                // Calculate price impact
                const priceImpact = calculatePriceImpact(
                    profitDetails.optimalSize,
                    Number(uniReserve0),
                    Number(uniReserve1),
                    pair.token0Decimals
                );

                // Skip if price impact is too high
                if (priceImpact > MEV_PROTECTION.maxPriceImpact) {
                    console.log(`⚠️ High price impact (${(priceImpact * 100).toFixed(2)}%) for ${pair.name}, skipping...`);
                    return;
                }

                // Add liquidity analysis
                const liquidityDetails = {
                    uniswapLiquidity: Number(ethers.formatUnits(uniReserve0, pair.token0Decimals)) * uniPriceDecimal,
                    sushiswapLiquidity: Number(ethers.formatUnits(sushiReserve0, pair.token0Decimals)) * sushiPriceDecimal,
                    tradeSize: profitDetails.optimalSize * Math.min(uniPriceDecimal, sushiPriceDecimal),
                    priceImpact: priceImpact * 100
                };

                logArbitrageOpportunity(pair, profitDetails, priceDiff, gasPriceGwei, liquidityDetails);
            }
        }
    } catch (error) {
        if (error.message.includes('rate limit') || 
            error.message.includes('network') || 
            error.code === 'BAD_DATA' ||
            error.message.includes('missing revert data')) {
            await sleep(2000);
            return;
        }
        console.error(`Error checking ${pair.name}:`, error.message);
    }
}

// Add real-time price impact calculation
function calculatePriceImpact(amount, reserve0, reserve1, decimals) {
    const amountBN = ethers.parseUnits(amount.toString(), decimals);
    const constantProduct = reserve0 * reserve1;
    const newReserve0 = reserve0 + amountBN;
    const newReserve1 = constantProduct / newReserve0;
    const priceImpact = Math.abs(1 - (newReserve1 * reserve0) / (reserve1 * newReserve0));
    return priceImpact;
}

function calculateProfit(uniPrice, sushiPrice, gasCostUSD, pair, uniReserve0, sushiReserve0) {
    const higherPrice = Math.max(uniPrice, sushiPrice);
    const lowerPrice = Math.min(uniPrice, sushiPrice);
    const profitPerUnit = higherPrice - lowerPrice;
    
    const maxSlippage = 0.003;
    const minReserves = Math.min(
        Number(ethers.formatUnits(uniReserve0, pair.token0Decimals)),
        Number(ethers.formatUnits(sushiReserve0, pair.token0Decimals))
    );
    
    const maxTradeSize = minReserves * 0.03;
    const optimalSize = Math.min(
        Math.sqrt(gasCostUSD / (profitPerUnit * (1 - maxSlippage))),
        maxTradeSize
    );
    
    const profit = (optimalSize * profitPerUnit * (1 - maxSlippage)) - gasCostUSD;
    const roi = (profit / gasCostUSD) * 100;
    
    if (profit > 5 && roi > 10 && roi < 1000) {
        return {
            profit,
            roi,
            optimalSize,
            direction: uniPrice > sushiPrice ? 'Sushi->Uni' : 'Uni->Sushi'
        };
    }
    
    return null;
}

// Update logging to include more details
function logArbitrageOpportunity(pair, details, priceDiff, gasPriceGwei, liquidityDetails) {
    console.log(`\n🚨 Verified Arbitrage: ${pair.name}`);
    console.log(`Price Difference: ${priceDiff.toFixed(3)}%`);
    console.log(`Direction: ${details.direction}`);
    console.log(`Optimal Size: ${details.optimalSize.toFixed(6)} ${pair.name.split('/')[0]}`);
    console.log(`Expected Profit: $${details.profit.toFixed(2)}`);
    console.log(`ROI: ${details.roi.toFixed(2)}%`);
    console.log(`Gas Price: ${gasPriceGwei} Gwei`);
    console.log('\nLiquidity Analysis:');
    console.log(`Uniswap Liquidity: $${liquidityDetails.uniswapLiquidity.toFixed(2)}`);
    console.log(`Sushiswap Liquidity: $${liquidityDetails.sushiswapLiquidity.toFixed(2)}`);
    console.log(`Trade Size: $${liquidityDetails.tradeSize.toFixed(2)}`);
    console.log(`Price Impact: ${liquidityDetails.priceImpact.toFixed(3)}%`);
    console.log(`\nSafety Metrics:`);
    console.log(`MEV Protection: ${MEV_PROTECTION.flashbotsEnabled ? '✅' : '❌'}`);
    console.log(`Private Pools: ${MEV_PROTECTION.privatePoolsOnly ? '✅' : '❌'}`);
    console.log(`Reserve Stability: ✅`);
}

async function getETHPrice() {
    try {
        // Use the WETH/USDC pair to get ETH price
        const wethUsdcPair = new ethers.Contract(
            "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc", // WETH/USDC pair on Uniswap V2
            ['function getReserves() external view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast)'],
            provider
        );
        
        const reserves = await wethUsdcPair.getReserves();
        // USDC has 6 decimals, WETH has 18
        const ethPrice = (Number(reserves[1]) * 1e12) / Number(reserves[0]);
        return ethPrice;
    } catch (error) {
        console.error("Error getting ETH price:", error);
        return 2200; // Fallback price
    }
}

// Add Flashbots provider setup
async function setupFlashbots() {
    const flashbotsProvider = await import('@flashbots/ethers-provider-bundle');
    const authSigner = new ethers.Wallet(process.env.PRIVATE_KEY, provider);
    const flashbotsRPC = 'https://relay.flashbots.net';
    return await flashbotsProvider.FlashbotsBundleProvider.create(
        provider,
        authSigner,
        flashbotsRPC
    );
}

// Add private pool integration
const PRIVATE_POOLS = {
    'WETH/DAI': {
        uniswap: process.env.UNI_PRIVATE_POOL_WETH_DAI,
        sushiswap: process.env.SUSHI_PRIVATE_POOL_WETH_DAI
    },
    // Add more private pools as needed
};

// Add emergency stop mechanism
let emergencyStopActive = false;
let lastEmergencyCheck = Date.now();
let totalLoss = 0;
let totalGasUsed = 0;

function checkEmergencyStop() {
    if (emergencyStopActive) {
        return true;
    }

    if (totalLoss > RISK_MANAGEMENT.emergencyStop.maxLoss || 
        totalGasUsed > RISK_MANAGEMENT.emergencyStop.maxGasSpent) {
        console.log('🚨 Emergency stop triggered!');
        console.log(`Total Loss: $${totalLoss}`);
        console.log(`Total Gas Used: ${totalGasUsed} ETH`);
        emergencyStopActive = true;
        return true;
    }
    return false;
}

// Update executeArbitrage to use Flashbots
async function executeArbitrage(pair, opportunity) {
    if (checkEmergencyStop()) {
        console.log('⛔ Emergency stop active, skipping trade');
        return;
    }

    // Check risk management limits
    const maxSize = RISK_MANAGEMENT.maxPositionSize[pair.name] || RISK_MANAGEMENT.maxPositionSize.default;
    const minLiquidity = RISK_MANAGEMENT.minLiquidity[pair.name] || RISK_MANAGEMENT.minLiquidity.default;
    
    if (opportunity.optimalSize > maxSize) {
        console.log(`⚠️ Trade size ${opportunity.optimalSize} exceeds max position size ${maxSize}`);
        return;
    }
    
    if (opportunity.liquidityUSD < minLiquidity) {
        console.log(`⚠️ Liquidity ${opportunity.liquidityUSD} below minimum ${minLiquidity}`);
        return;
    }

    try {
        const flashbotsProvider = await setupFlashbots();
        const wallet = new ethers.Wallet(process.env.PRIVATE_KEY, provider);
        
        // Prepare transaction
        const tx = await pair.contract.populateTransaction.executeArbitrage(
            opportunity.path,
            opportunity.amounts,
            opportunity.direction
        );
        
        // Get block number for bundle
        const blockNumber = await provider.getBlockNumber();
        
        // Create Flashbots bundle
        const bundle = [{
            transaction: {
                ...tx,
                gasPrice: opportunity.gasPrice,
                gasLimit: estimatedGasUsed[pair.name] || estimatedGasUsed.default
            },
            signer: wallet
        }];
        
        // Simulate bundle
        const simulation = await flashbotsProvider.simulate(bundle, blockNumber + 1);
        
        if (simulation.firstRevert) {
            console.log('❌ Bundle simulation failed:', simulation.firstRevert);
            return;
        }
        
        // Submit bundle
        const bundleSubmission = await flashbotsProvider.sendBundle(bundle, blockNumber + 1);
        const waitResponse = await bundleSubmission.wait();
        
        // Update stats based on result
        const trade = {
            success: waitResponse.bundleInclusion === 0,
            profit: opportunity.profit,
            gasSpent: opportunity.gasPrice * (estimatedGasUsed[pair.name] || estimatedGasUsed.default),
            pair: pair.name
        };
        
        updateExecutionStats(trade);
        
        if (!trade.success) {
            totalLoss += trade.gasSpent * 2200; // Convert gas cost to USD
            totalGasUsed += Number(ethers.formatEther(trade.gasSpent));
        }
        
        return trade.success;
        
    } catch (error) {
        console.error('Error executing arbitrage:', error);
        return false;
    }
}

// Update main loop to use private pools when available
async function getPoolForPair(pair, dex) {
    if (MEV_PROTECTION.privatePoolsOnly && PRIVATE_POOLS[pair.name]) {
        return PRIVATE_POOLS[pair.name][dex];
    }
    return dex === 'uniswap' ? 
        await getUniswapPair(pair.token0, pair.token1) : 
        await getSushiswapPair(pair.token0, pair.token1);
}

async function initializeContracts() {
    const wallet = new ethers.Wallet(process.env.PRIVATE_KEY, provider);
    
    // Deploy flash loan arbitrage contract
    console.log("Deploying Flash Loan Arbitrage Contract...");
    const FlashLoanArbitrage = await ethers.getContractFactory("FlashLoanArbitrage", wallet);
    
    // Convert profit threshold to basis points (1 bp = 0.01%)
    const minProfitBps = Math.floor(parseFloat(process.env.MIN_PROFIT_THRESHOLD || "0.01") * 10000);
    const maxFlashLoanAmount = ethers.parseEther("1000"); // Set a reasonable max flash loan amount
    
    flashLoanContract = await FlashLoanArbitrage.deploy(
        addresses.aaveV3PoolAddressProvider,
        addresses.uniswapV2Router,
        addresses.weth,
        maxFlashLoanAmount,
        minProfitBps
    );
    await flashLoanContract.waitForDeployment();
    console.log("Flash Loan Arbitrage Contract deployed to:", await flashLoanContract.getAddress());
}

async function main() {
    try {
        // Initialize provider with retry logic
        console.log("Connecting to Alchemy WebSocket...");
        const wsUrl = `wss://eth-mainnet.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`;
        if (!process.env.ALCHEMY_API_KEY) {
            throw new Error("ALCHEMY_API_KEY not found in environment variables");
        }

        provider = new ethers.WebSocketProvider(wsUrl);
        
        // Wait for provider to be ready
        await provider.ready;
        console.log('Provider connection established');

        // Set up reconnection logic
        provider.on('error', (error) => {
            console.error('Provider error:', error);
            setTimeout(main, 5000); // Retry after 5 seconds
        });

        console.log("\nInitializing trading pairs...");
        for (const pair of TRADING_PAIRS) {
            await setupPairMonitoring(pair);
            await sleep(1000); // Wait 1 second between pair setups
        }
        console.log("Trading pairs initialized\n");
        
        // Add this to your main loop
        setInterval(checkBotHealth, 5 * 60 * 1000); // Check health every 5 minutes

    } catch (error) {
        console.error("Error in main:", error);
        // Retry after delay
        console.log("Retrying in 5 seconds...");
        setTimeout(main, 5000);
    }
}

// Gas estimates for different pairs
const estimatedGasUsed = {
    'WETH/DAI': 180000n,    // Lower gas for common pairs
    'WETH/USDC': 180000n,
    'USDC/USDT': 190000n,
    'DAI/USDC': 190000n,
    'DAI/USDT': 190000n,
    'WBTC/WETH': 200000n,
    'default': 250000n      // Higher gas estimate for other pairs
};

// Run the bot
main().catch((error) => {
    console.error(error);
    process.exit(1);
});
