const { ethers } = require("hardhat");
const addresses = require("./addresses");

const ERC20_ABI = [
    "function symbol() external view returns (string)",
    "function decimals() external view returns (uint8)",
    "function balanceOf(address account) external view returns (uint256)"
];

async function main() {
    const [signer] = await ethers.getSigners();
    console.log("Using account:", signer.address);

    // Verify USDC
    try {
        const usdc = await ethers.getContractAt(ERC20_ABI, addresses.usdc);
        const symbol = await usdc.symbol();
        const decimals = await usdc.decimals();
        const balance = await usdc.balanceOf(signer.address);
        
        console.log("\nUSDC Contract Info:");
        console.log("Address:", addresses.usdc);
        console.log("Symbol:", symbol);
        console.log("Decimals:", decimals);
        console.log("Balance:", ethers.formatUnits(balance, decimals));
    } catch (error) {
        console.error("Error checking USDC:", error.message);
    }

    // Verify DAI
    try {
        const dai = await ethers.getContractAt(ERC20_ABI, addresses.dai);
        const symbol = await dai.symbol();
        const decimals = await dai.decimals();
        const balance = await dai.balanceOf(signer.address);
        
        console.log("\nDAI Contract Info:");
        console.log("Address:", addresses.dai);
        console.log("Symbol:", symbol);
        console.log("Decimals:", decimals);
        console.log("Balance:", ethers.formatUnits(balance, decimals));
    } catch (error) {
        console.error("Error checking DAI:", error.message);
    }

    // Verify WETH
    try {
        const weth = await ethers.getContractAt(ERC20_ABI, addresses.weth);
        const symbol = await weth.symbol();
        const decimals = await weth.decimals();
        const balance = await weth.balanceOf(signer.address);
        
        console.log("\nWETH Contract Info:");
        console.log("Address:", addresses.weth);
        console.log("Symbol:", symbol);
        console.log("Decimals:", decimals);
        console.log("Balance:", ethers.formatUnits(balance, decimals));
    } catch (error) {
        console.error("Error checking WETH:", error.message);
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
