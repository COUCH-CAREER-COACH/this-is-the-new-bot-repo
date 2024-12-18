const { ethers } = require("hardhat");

const POOL_ABI = [
    "function getReservesList() external view returns (address[])",
    "function getReserveData(address asset) external view returns (tuple(uint256 configuration, uint128 liquidityIndex, uint128 currentLiquidityRate, uint128 variableBorrowIndex, uint128 currentVariableBorrowRate, uint128 currentStableBorrowRate, uint40 lastUpdateTimestamp, uint16 id, address aTokenAddress, address stableDebtTokenAddress, address variableDebtTokenAddress, address interestRateStrategyAddress, uint128 accruedToTreasury, uint128 unbacked, uint128 isolationModeTotalDebt))"
];

const ERC20_ABI = [
    "function symbol() external view returns (string)",
    "function decimals() external view returns (uint8)"
];

async function main() {
    console.log("\nQuerying Aave V3 Sepolia Pool...");

    // Aave V3 Pool address on Sepolia
    const poolAddress = "0x6Ae43d3271ff6888e7Fc43Fd7321a503ff738951";
    const pool = await ethers.getContractAt(POOL_ABI, poolAddress);
    
    try {
        // Get all reserves
        const reserves = await pool.getReservesList();
        console.log("\nConfigured tokens:");
        
        for (const tokenAddress of reserves) {
            const token = await ethers.getContractAt(ERC20_ABI, tokenAddress);
            const symbol = await token.symbol();
            const decimals = await token.decimals();
            const reserveData = await pool.getReserveData(tokenAddress);
            
            console.log(`\nToken: ${symbol}`);
            console.log(`Address: ${tokenAddress}`);
            console.log(`Decimals: ${decimals}`);
            console.log(`aToken Address: ${reserveData.aTokenAddress}`);
            console.log(`Variable Debt Token: ${reserveData.variableDebtTokenAddress}`);
        }
    } catch (error) {
        console.error("Error:", error);
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
