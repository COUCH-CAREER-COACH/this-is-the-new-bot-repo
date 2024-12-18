const { ethers } = require("hardhat");

const POOL_DATA_PROVIDER_ABI = [
    "function getAllReservesTokens() external view returns (tuple(string symbol, address tokenAddress)[])",
    "function getReserveConfigurationData(address asset) external view returns (tuple(uint256 decimals, uint256 ltv, uint256 liquidationThreshold, uint256 liquidationBonus, uint256 reserveFactor, bool usageAsCollateralEnabled, bool borrowingEnabled, bool stableBorrowRateEnabled, bool isActive, bool isFrozen))"
];

async function main() {
    console.log("\nListing all tokens in Aave V3 Sepolia Pool...");

    // Get Pool Data Provider contract - Updated to correct Sepolia address
    const dataProviderAddress = "0x8f57153F18b7273f9A814b93b31Cb3f9b035e7C2";
    const dataProvider = await ethers.getContractAt(POOL_DATA_PROVIDER_ABI, dataProviderAddress);
    
    try {
        // Get all reserves
        const reserves = await dataProvider.getAllReservesTokens();
        console.log("\nConfigured tokens:");
        
        for (const reserve of reserves) {
            console.log(`\nToken: ${reserve.symbol}`);
            console.log(`Address: ${reserve.tokenAddress}`);
            
            try {
                const config = await dataProvider.getReserveConfigurationData(reserve.tokenAddress);
                console.log("Configuration:");
                console.log("- Decimals:", config.decimals);
                console.log("- LTV:", config.ltv);
                console.log("- Active:", config.isActive);
                console.log("- Frozen:", config.isFrozen);
                console.log("- Borrowing Enabled:", config.borrowingEnabled);
            } catch (error) {
                console.log("Error getting config:", error.message);
            }
        }
    } catch (error) {
        console.error("Error getting reserve tokens:", error);
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
