const { ethers } = require("hardhat");
const addresses = require("./addresses");

// Uniswap V2 Router ABI (only what we need)
const ROUTER_ABI = [
    "function getAmountsOut(uint amountIn, address[] memory path) public view returns (uint[] memory amounts)",
    "function getAmountsIn(uint amountOut, address[] memory path) public view returns (uint[] memory amounts)",
    "function factory() external pure returns (address)"
];

// Token ABI
const ERC20_ABI = [
    "function decimals() external view returns (uint8)",
    "function symbol() external view returns (string)"
];

async function main() {
    const [signer] = await ethers.getSigners();
    console.log("Using account:", signer.address);

    // Connect to Uniswap router
    const uniswapRouter = await ethers.getContractAt(ROUTER_ABI, addresses.uniswapV2Router);
    
    // Get factory address
    try {
        const factoryAddress = await uniswapRouter.factory();
        console.log("Uniswap factory address:", factoryAddress);
    } catch (error) {
        console.log("Error getting factory:", error.message);
    }

    // Connect to tokens
    const dai = await ethers.getContractAt(ERC20_ABI, addresses.dai);
    const usdc = await ethers.getContractAt(ERC20_ABI, addresses.usdc);
    const weth = await ethers.getContractAt(ERC20_ABI, addresses.weth);

    // Get decimals
    const daiDecimals = await dai.decimals();
    const usdcDecimals = await usdc.decimals();
    const wethDecimals = await weth.decimals();

    // Test amounts
    const testAmounts = {
        dai: ethers.parseUnits("1000", daiDecimals),
        usdc: ethers.parseUnits("1000", usdcDecimals),
        weth: ethers.parseUnits("1", wethDecimals)
    };

    // Check prices on Uniswap
    console.log("\nChecking DAI -> USDC on Uniswap");
    try {
        const amounts = await uniswapRouter.getAmountsOut(
            testAmounts.dai,
            [addresses.dai, addresses.usdc]
        );
        const amountOut = amounts[1];
        const price = ethers.formatUnits(amountOut, usdcDecimals) / ethers.formatUnits(testAmounts.dai, daiDecimals);
        console.log("Price:", price);
    } catch (error) {
        console.log("Error:", error.message);
    }

    console.log("\nChecking WETH -> DAI on Uniswap");
    try {
        const amounts = await uniswapRouter.getAmountsOut(
            testAmounts.weth,
            [addresses.weth, addresses.dai]
        );
        const amountOut = amounts[1];
        const price = ethers.formatUnits(amountOut, daiDecimals) / ethers.formatUnits(testAmounts.weth, wethDecimals);
        console.log("Price:", price);
    } catch (error) {
        console.log("Error:", error.message);
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
