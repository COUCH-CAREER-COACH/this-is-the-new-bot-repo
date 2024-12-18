const { ethers } = require("hardhat");
require("dotenv").config();

async function checkArbitrageOpportunity(flashLoanArbitrage, token0, token1, router, amount) {
    try {
        // Get token decimals
        const token0Contract = await ethers.getContractAt("MockERC20", token0);
        const token1Contract = await ethers.getContractAt("MockERC20", token1);
        const decimals0 = await token0Contract.decimals();
        const decimals1 = await token1Contract.decimals();

        console.log(`\nChecking arbitrage opportunity for ${await token0Contract.symbol()} -> ${await token1Contract.symbol()}`);
        console.log(`Amount: ${amount} ${await token0Contract.symbol()}`);

        // Create path arrays for both directions
        const path0to1 = [token0, token1];
        const path1to0 = [token1, token0];

        // Get amounts out for the complete cycle
        const amountIn = ethers.parseUnits(amount.toString(), decimals0);
        const amountsOut0to1 = await router.getAmountsOut(amountIn, path0to1);
        const amountsOut1to0 = await router.getAmountsOut(amountsOut0to1[1], path1to0);

        // Calculate potential profit
        const finalAmount = amountsOut1to0[1];
        const profit = finalAmount - amountIn;

        // Calculate profit percentage
        const profitPercentage = (profit * BigInt(10000)) / amountIn;

        console.log(`Expected output: ${ethers.formatUnits(finalAmount, decimals0)} ${await token0Contract.symbol()}`);
        console.log(`Expected profit: ${ethers.formatUnits(profit, decimals0)} ${await token0Contract.symbol()} (${Number(profitPercentage) / 100}%)`);

        // Check if profit meets minimum requirement (default 1%)
        const minProfitBps = await flashLoanArbitrage.minProfitBps();
        if (profitPercentage >= minProfitBps) {
            console.log(`Profitable opportunity found! Profit percentage: ${Number(profitPercentage) / 100}%`);
            return {
                profitable: true,
                inputToken: token0,
                amount: amountIn,
                expectedProfit: profit,
                profitPercentage: Number(profitPercentage) / 100,
                decimals: decimals0,
                symbol: await token0Contract.symbol()
            };
        }

        return { profitable: false };
    } catch (error) {
        console.error("Error checking arbitrage opportunity:", error);
        return { profitable: false };
    }
}

async function executeArbitrage(flashLoanArbitrage, opportunity) {
    try {
        // Get signer
        const [signer] = await ethers.getSigners();
        
        // Get token contract
        const tokenContract = await ethers.getContractAt("MockERC20", opportunity.inputToken);
        
        // Fetch token balance of Aave pool
        const aavePool = await flashLoanArbitrage.POOL();
        const poolBalance = await tokenContract.balanceOf(aavePool);
        console.log(`\nAave pool balance: ${ethers.formatUnits(poolBalance, opportunity.decimals)} ${opportunity.symbol}`);
        
        // Check if pool has enough tokens
        if (poolBalance < opportunity.amount) {
            console.error(`Insufficient pool balance. Required: ${ethers.formatUnits(opportunity.amount, opportunity.decimals)}, Available: ${ethers.formatUnits(poolBalance, opportunity.decimals)}`);
            return;
        }

        // Fetch ETH balance of signer
        const ethBalance = await signer.provider.getBalance(signer.address);
        console.log(`Signer ETH balance: ${ethers.formatEther(ethBalance)} ETH`);

        // Estimate gas
        const gasPrice = await signer.provider.getFeeData().then(data => data.gasPrice);
        const gasLimit = 1000000n;
        const gasCost = gasPrice * gasLimit;
        console.log(`Estimated gas cost: ${ethers.formatEther(gasCost)} ETH`);

        // Check if signer has enough ETH for gas
        if (ethBalance < gasCost) {
            console.error(`Insufficient ETH for gas. Required: ${ethers.formatEther(gasCost)}, Available: ${ethers.formatEther(ethBalance)}`);
            return;
        }

        console.log(`\nExecuting arbitrage trade:`);
        console.log(`Input amount: ${ethers.formatUnits(opportunity.amount, opportunity.decimals)} ${opportunity.symbol}`);
        console.log(`Expected profit: ${ethers.formatUnits(opportunity.expectedProfit, opportunity.decimals)} ${opportunity.symbol} (${opportunity.profitPercentage}%)`);
        
        // Execute flash loan with gas settings
        const tx = await flashLoanArbitrage.initiateFlashLoan(
            opportunity.inputToken,
            opportunity.amount,
            { gasLimit, gasPrice }
        );
        
        console.log(`Transaction submitted! Hash: ${tx.hash}`);
        const receipt = await tx.wait();
        console.log(`Transaction confirmed! Gas used: ${receipt.gasUsed}`);
        console.log("Arbitrage executed successfully!");
        
    } catch (error) {
        console.error("Error executing arbitrage:", error.reason || error.message);
        // Log additional error details if available
        if (error.data) {
            console.error("Error data:", error.data);
        }
        if (error.transaction) {
            console.error("Failed transaction:", {
                from: error.transaction.from,
                to: error.transaction.to,
                value: error.transaction.value?.toString(),
                data: error.transaction.data
            });
        }
    }
}

async function checkTokenBalances(addresses) {
    console.log("\nChecking token balances in Aave pool...");
    
    const weth = await ethers.getContractAt("MockWETH", addresses.weth);
    const dai = await ethers.getContractAt("MockERC20", addresses.dai);
    const usdc = await ethers.getContractAt("MockERC20", addresses.usdc);
    
    const wethBalance = await weth.balanceOf(addresses.aavePool);
    const daiBalance = await dai.balanceOf(addresses.aavePool);
    const usdcBalance = await usdc.balanceOf(addresses.aavePool);
    
    console.log(`WETH balance: ${ethers.formatEther(wethBalance)} WETH`);
    console.log(`DAI balance: ${ethers.formatEther(daiBalance)} DAI`);
    console.log(`USDC balance: ${ethers.formatUnits(usdcBalance, 6)} USDC`);
    
    return {
        weth: wethBalance,
        dai: daiBalance,
        usdc: usdcBalance
    };
}

async function monitorArbitrageOpportunities() {
    try {
        // Load addresses
        const addresses = require("../deployment-addresses.json");
        
        // Get contract instances
        const router = await ethers.getContractAt("MockUniswapV2Router02", addresses.router);
        const flashLoanArbitrage = await ethers.getContractAt("FlashLoanArbitrage", addresses.flashLoanArbitrage);

        // Token pairs to monitor
        const pairs = [
            { token0: addresses.dai, token1: addresses.usdc },
            { token0: addresses.weth, token1: addresses.dai },
            { token0: addresses.weth, token1: addresses.usdc }
        ];

        // Test amounts (in token0 decimals)
        const testAmounts = [0.1, 0.5, 1, 5];

        console.log("\n=== Starting Arbitrage Bot ===");
        console.log("Monitoring pairs:");
        console.log("1. DAI/USDC");
        console.log("2. WETH/DAI");
        console.log("3. WETH/USDC");
        console.log("\nTest amounts:", testAmounts);
        console.log("\nMonitoring for arbitrage opportunities...");

        // Check token balances in Aave pool
        await checkTokenBalances(addresses);

        // Monitor continuously
        while (true) {
            for (const pair of pairs) {
                for (const amount of testAmounts) {
                    const opportunity = await checkArbitrageOpportunity(
                        flashLoanArbitrage,
                        pair.token0,
                        pair.token1,
                        router,
                        amount
                    );

                    if (opportunity.profitable) {
                        await executeArbitrage(flashLoanArbitrage, opportunity);
                    }
                }
            }

            // Wait before next check
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    } catch (error) {
        console.error("Error in monitoring loop:", error);
    }
}

// Main function
async function main() {
    // Load addresses
    const addresses = require("../deployment-addresses.json");
    
    // Check token balances first
    await checkTokenBalances(addresses);
    
    // Start monitoring
    await monitorArbitrageOpportunities();
}

// Execute main function
main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
