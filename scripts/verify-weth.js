const { ethers } = require("hardhat");
const addresses = require("./addresses");

const ERC20_ABI = [
    "function symbol() view returns (string)",
    "function decimals() view returns (uint8)",
    "function balanceOf(address) view returns (uint256)",
    "function totalSupply() view returns (uint256)"
];

async function main() {
    console.log("\nVerifying WETH on Sepolia...");

    const [signer] = await ethers.getSigners();
    console.log("Using account:", signer.address);

    // Get Pool contract
    const pool = await ethers.getContractAt("IPool", addresses.aaveProvider);
    
    try {
        // Get WETH contract
        const wethContract = await ethers.getContractAt(ERC20_ABI, addresses.weth);
        
        // Get basic token info
        const symbol = await wethContract.symbol();
        const decimals = await wethContract.decimals();
        const balance = await wethContract.balanceOf(signer.address);
        const totalSupply = await wethContract.totalSupply();
        
        console.log("\nWETH Token Info:");
        console.log("- Address:", addresses.weth);
        console.log("- Symbol:", symbol);
        console.log("- Decimals:", decimals);
        console.log("- Balance:", ethers.formatUnits(balance, decimals));
        console.log("- Total Supply:", ethers.formatUnits(totalSupply, decimals));
        
        // Try to get reserve data
        try {
            const reserveData = await pool.getReserveData(addresses.weth);
            console.log("\nAave Configuration:");
            console.log("- aToken:", reserveData.aTokenAddress);
            console.log("- stableDebtToken:", reserveData.stableDebtTokenAddress);
            console.log("- variableDebtToken:", reserveData.variableDebtTokenAddress);
            console.log("\nWETH is configured in Aave! ✅");
        } catch (error) {
            console.log("\nError: WETH is not configured in Aave ❌");
            console.error(error.message);
        }
    } catch (error) {
        console.log("Error getting WETH info:", error.message);
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
