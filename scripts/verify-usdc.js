const { ethers } = require("hardhat");
const addresses = require("./addresses");

const ERC20_ABI = [
    "function symbol() view returns (string)",
    "function decimals() view returns (uint8)",
    "function balanceOf(address) view returns (uint256)",
    "function totalSupply() view returns (uint256)"
];

async function main() {
    console.log("\nVerifying USDC on Sepolia...");

    const [signer] = await ethers.getSigners();
    console.log("Using account:", signer.address);

    // Get Pool contract
    const pool = await ethers.getContractAt("IPool", addresses.aaveProvider);
    
    try {
        // Get USDC contract
        const usdcContract = await ethers.getContractAt(ERC20_ABI, addresses.usdc);
        
        // Get basic token info
        const symbol = await usdcContract.symbol();
        const decimals = await usdcContract.decimals();
        const balance = await usdcContract.balanceOf(signer.address);
        const totalSupply = await usdcContract.totalSupply();
        
        console.log("\nUSDC Token Info:");
        console.log("- Address:", addresses.usdc);
        console.log("- Symbol:", symbol);
        console.log("- Decimals:", decimals);
        console.log("- Balance:", ethers.formatUnits(balance, decimals));
        console.log("- Total Supply:", ethers.formatUnits(totalSupply, decimals));
        
        // Try to get reserve data
        try {
            const reserveData = await pool.getReserveData(addresses.usdc);
            console.log("\nAave Configuration:");
            console.log("- aToken:", reserveData.aTokenAddress);
            console.log("- stableDebtToken:", reserveData.stableDebtTokenAddress);
            console.log("- variableDebtToken:", reserveData.variableDebtTokenAddress);
            console.log("\nUSDC is configured in Aave! ✅");
        } catch (error) {
            console.log("\nError: USDC is not configured in Aave ❌");
            console.error(error.message);
        }
    } catch (error) {
        console.log("Error getting USDC info:", error.message);
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
