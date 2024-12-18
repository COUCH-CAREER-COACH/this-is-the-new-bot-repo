const { ethers } = require("hardhat");
const addresses = require("./addresses");

async function main() {
    const [signer] = await ethers.getSigners();
    console.log("Checking Aave configuration...");

    // Get Pool contract
    const poolAbi = [
        "function getReserveData(address asset) view returns (tuple(uint256 configuration, uint128 liquidityIndex, uint128 currentLiquidityRate, uint128 variableBorrowIndex, uint128 currentVariableBorrowRate, uint128 currentStableBorrowRate, uint40 lastUpdateTimestamp, address aTokenAddress, address stableDebtTokenAddress, address variableDebtTokenAddress, address interestRateStrategyAddress, uint8 id))",
        "function supply(address asset, uint256 amount, address onBehalfOf, uint16 referralCode) external"
    ];
    const pool = new ethers.Contract(addresses.aaveProvider, poolAbi, signer);

    // Check both DAI tokens
    const daiTokens = [
        { name: "Aave DAI", address: "0x68194a729C2450ad26072b3D33ADaCbcef39D574" },
        { name: "Faucet DAI", address: "0xff34b3d4aee8ddcd6f9afffb6fe49bd371b8a357" }
    ];

    for (const dai of daiTokens) {
        console.log(`\nChecking ${dai.name} (${dai.address})...`);
        try {
            const reserveData = await pool.getReserveData(dai.address);
            console.log("Reserve configuration:", reserveData);
            console.log("Token is configured in Aave!");
        } catch (e) {
            console.log("Token is not configured in Aave:", e.message);
        }
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
