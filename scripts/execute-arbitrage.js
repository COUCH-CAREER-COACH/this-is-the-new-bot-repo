const { ethers } = require("hardhat");
const addresses = require("./addresses");

// Add delay between requests to avoid rate limiting
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function checkPrice(router, tokenIn, tokenOut, amountIn, decimalsIn, decimalsOut, symbolIn, symbolOut) {
    try {
        await delay(1000); // Add 1 second delay between price checks
        const amounts = await router.getAmountsOut(amountIn, [tokenIn, tokenOut]);
        const price = ethers.formatUnits(amounts[1], decimalsOut);
        console.log(`Price for ${ethers.formatUnits(amountIn, decimalsIn)} ${symbolIn} = ${price} ${symbolOut}`);
        return amounts[1];
    } catch (error) {
        console.log(`Error checking price for ${symbolIn}/${symbolOut}:`, error.message);
        return null;
    }
}

async function checkDEX(name, router, factory, pairs) {
    console.log(`\n=== Checking ${name} ===`);
    console.log("Factory:", factory.address);
    console.log("Router:", router.address);

    for (const pair of pairs) {
        console.log(`\n--- ${pair.symbolA}/${pair.symbolB} Pair ---`);
        
        await delay(1000);
        const pairAddress = await factory.getPair(pair.tokenA, pair.tokenB);
        console.log("Pool address:", pairAddress);

        if (pairAddress === "0x0000000000000000000000000000000000000000") {
            console.log("Pool not found");
            continue;
        }

        const pairContract = await ethers.getContractAt(PAIR_ABI, pairAddress);
        await delay(1000);
        const [reserve0, reserve1] = await pairContract.getReserves();
        await delay(1000);
        const token0 = await pairContract.token0();
        await delay(1000);
        const token1 = await pairContract.token1();

        console.log("\nPool reserves:");
        if (token0.toLowerCase() === pair.tokenA.toLowerCase()) {
            console.log(`- ${pair.symbolA}: ${ethers.formatUnits(reserve0, pair.decimalsA)}`);
            console.log(`- ${pair.symbolB}: ${ethers.formatUnits(reserve1, pair.decimalsB)}`);
        } else {
            console.log(`- ${pair.symbolA}: ${ethers.formatUnits(reserve1, pair.decimalsA)}`);
            console.log(`- ${pair.symbolB}: ${ethers.formatUnits(reserve0, pair.decimalsB)}`);
        }

        // Check different amounts
        console.log("\nChecking prices:");
        const baseAmount = pair.symbolA === "WETH" ? "0.1" : "100";
        const amounts = [
            ethers.parseUnits(baseAmount, pair.decimalsA),      // Base amount
            ethers.parseUnits((parseFloat(baseAmount) * 5).toString(), pair.decimalsA),  // 5x
            ethers.parseUnits((parseFloat(baseAmount) * 10).toString(), pair.decimalsA), // 10x
        ];

        console.log(`\n${pair.symbolA} → ${pair.symbolB}:`);
        for (const amount of amounts) {
            await checkPrice(router, pair.tokenA, pair.tokenB, amount, pair.decimalsA, pair.decimalsB, pair.symbolA, pair.symbolB);
        }

        console.log(`\n${pair.symbolB} → ${pair.symbolA}:`);
        const reverseAmounts = amounts.map(amt => 
            ethers.parseUnits(ethers.formatUnits(amt, pair.decimalsA), pair.decimalsB)
        );
        for (const amount of reverseAmounts) {
            await checkPrice(router, pair.tokenB, pair.tokenA, amount, pair.decimalsB, pair.decimalsA, pair.symbolB, pair.symbolA);
        }
    }
}

async function main() {
    try {
        const [signer] = await ethers.getSigners();
        console.log("Using account:", signer.address);

        // Connect to contracts
        const uniswapRouter = await ethers.getContractAt(ROUTER_ABI, addresses.uniswapV2Router);
        const uniFactory = await ethers.getContractAt(FACTORY_ABI, addresses.uniswapFactory);
        const sushiRouter = await ethers.getContractAt(ROUTER_ABI, addresses.sushiRouter);
        const sushiFactory = await ethers.getContractAt(FACTORY_ABI, addresses.sushiFactory);

        // Get token contracts and information
        const dai = await ethers.getContractAt(ERC20_ABI, addresses.dai);
        const usdc = await ethers.getContractAt(ERC20_ABI, addresses.usdc);
        const weth = await ethers.getContractAt(ERC20_ABI, addresses.weth);
        
        const daiSymbol = await dai.symbol();
        const usdcSymbol = await usdc.symbol();
        const wethSymbol = await weth.symbol();
        
        const daiDecimals = await dai.decimals();
        const usdcDecimals = await usdc.decimals();
        const wethDecimals = await weth.decimals();

        // Define pairs to check
        const pairs = [
            {
                tokenA: addresses.dai,
                tokenB: addresses.usdc,
                symbolA: daiSymbol,
                symbolB: usdcSymbol,
                decimalsA: daiDecimals,
                decimalsB: usdcDecimals,
            },
            {
                tokenA: addresses.weth,
                tokenB: addresses.usdc,
                symbolA: wethSymbol,
                symbolB: usdcSymbol,
                decimalsA: wethDecimals,
                decimalsB: usdcDecimals,
            },
            {
                tokenA: addresses.weth,
                tokenB: addresses.dai,
                symbolA: wethSymbol,
                symbolB: daiSymbol,
                decimalsA: wethDecimals,
                decimalsB: daiDecimals,
            }
        ];

        // Check both DEXes
        await checkDEX("Uniswap V2", uniswapRouter, uniFactory, pairs);
        await checkDEX("Sushiswap", sushiRouter, sushiFactory, pairs);

        console.log("\nNote: All prices shown are from mainnet fork");
        
    } catch (error) {
        console.error("\nError:", error.message);
        if (error.data) {
            console.error("Error data:", error.data);
        }
        process.exit(1);
    }
}

// ABIs
const ROUTER_ABI = [
    "function getAmountsOut(uint amountIn, address[] memory path) public view returns (uint[] memory amounts)",
    "function factory() external view returns (address)"
];

const FACTORY_ABI = [
    "function getPair(address tokenA, address tokenB) external view returns (address)"
];

const PAIR_ABI = [
    "function getReserves() external view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast)",
    "function token0() external view returns (address)",
    "function token1() external view returns (address)"
];

const ERC20_ABI = [
    "function decimals() external view returns (uint8)",
    "function balanceOf(address account) external view returns (uint256)",
    "function approve(address spender, uint256 amount) external returns (bool)",
    "function symbol() external view returns (string)"
];

main()
    .then(() => process.exit(0))
    .catch(error => {
        console.error(error);
        process.exit(1);
    });
