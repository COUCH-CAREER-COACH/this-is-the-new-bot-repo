const { ethers } = require("hardhat");

async function main() {
    const addresses = require("../deployment-addresses.json");
    
    // Get contract instances
    const router = await ethers.getContractAt("MockUniswapV2Router02", addresses.router);
    const weth = await ethers.getContractAt("MockWETH", addresses.weth);
    const dai = await ethers.getContractAt("MockERC20", addresses.dai);
    const usdc = await ethers.getContractAt("MockERC20", addresses.usdc);
    const flashLoanArbitrage = await ethers.getContractAt("FlashLoanArbitrage", addresses.flashLoanArbitrage);
    
    console.log("Setting exchange rates to create arbitrage opportunities...");
    
    // Set exchange rates to create arbitrage opportunity
    // DAI/USDC: 1 DAI = 1.2 USDC on first trade, 1 USDC = 0.9 DAI on second trade (20% profit potential)
    await router.setPrice(
        addresses.dai,
        addresses.usdc,
        ethers.parseUnits("1.2", 18)  // DAI to USDC
    );
    await router.setPrice(
        addresses.usdc,
        addresses.dai,
        ethers.parseUnits("0.9", 18)  // USDC to DAI
    );
    console.log("Set DAI/USDC exchange rates");

    // WETH/DAI: 1 WETH = 2200 DAI on first trade, 1 DAI = 0.00042 WETH on second trade (15% profit potential)
    await router.setPrice(
        addresses.weth,
        addresses.dai,
        ethers.parseUnits("2200", 18)  // WETH to DAI
    );
    await router.setPrice(
        addresses.dai,
        addresses.weth,
        ethers.parseUnits("0.00042", 18)  // DAI to WETH
    );
    console.log("Set WETH/DAI exchange rates");

    // WETH/USDC: 1 WETH = 2400 USDC on first trade, 1 USDC = 0.00038 WETH on second trade (10% profit potential)
    await router.setPrice(
        addresses.weth,
        addresses.usdc,
        ethers.parseUnits("2400", 18)  // WETH to USDC
    );
    await router.setPrice(
        addresses.usdc,
        addresses.weth,
        ethers.parseUnits("0.00038", 18)  // USDC to WETH
    );
    console.log("Set WETH/USDC exchange rates");

    console.log("Successfully set all mock prices!");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
