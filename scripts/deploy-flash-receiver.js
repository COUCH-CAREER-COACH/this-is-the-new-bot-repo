const { ethers } = require("hardhat");
const addresses = require("./addresses");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log("Deploying FlashLoanReceiver with account:", deployer.address);

    const FlashLoanReceiver = await ethers.getContractFactory("FlashLoanReceiver");
    console.log("Deploying...");
    const flashLoanReceiver = await FlashLoanReceiver.deploy(
        addresses.aaveProvider,
        addresses.uniswapV2Router,
        addresses.sushiswapRouter
    );
    
    console.log("Waiting for deployment...");
    await flashLoanReceiver.waitForDeployment();
    
    const address = await flashLoanReceiver.getAddress();
    console.log("FlashLoanReceiver deployed to:", address);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
