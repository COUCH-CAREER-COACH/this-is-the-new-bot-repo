const { ethers } = require("hardhat");

const ERC20_ABI = [
    "function symbol() view returns (string)",
    "function decimals() view returns (uint8)",
    "function balanceOf(address) view returns (uint256)",
    "function totalSupply() view returns (uint256)"
];

async function main() {
    console.log("\nVerifying DAI tokens on Sepolia...");

    // List of DAI addresses to check
    const daiAddresses = [
        "0xff34b3d4aee8ddcd6f9afffb6fe49bd371b8a357", // Faucet DAI
        "0x68194a729C2450ad26072b3D33ADaCbcef39D574", // Previous DAI
        "0x3e622317f8C93f7328350cF0B56d9eD4C620C5d6"  // Another DAI variant
    ];

    const [signer] = await ethers.getSigners();
    console.log("Using account:", signer.address);

    // Get Pool contract
    const poolAddress = "0x0496275d34753A48320CA58103d5220d394FF77F";
    const pool = await ethers.getContractAt("IPool", poolAddress);
    
    for (const daiAddress of daiAddresses) {
        console.log(`\nChecking DAI at ${daiAddress}...`);
        
        try {
            // Get DAI contract
            const daiContract = await ethers.getContractAt(ERC20_ABI, daiAddress);
            
            // Get basic token info
            const symbol = await daiContract.symbol();
            const decimals = await daiContract.decimals();
            const balance = await daiContract.balanceOf(signer.address);
            const totalSupply = await daiContract.totalSupply();
            
            console.log("Token Info:");
            console.log("- Symbol:", symbol);
            console.log("- Decimals:", decimals);
            console.log("- Balance:", ethers.formatUnits(balance, decimals));
            console.log("- Total Supply:", ethers.formatUnits(totalSupply, decimals));
            
            // Try to get reserve data
            try {
                const reserveData = await pool.getReserveData(daiAddress);
                console.log("\nAave Configuration:");
                console.log("- aToken:", reserveData.aTokenAddress);
                console.log("- stableDebtToken:", reserveData.stableDebtTokenAddress);
                console.log("- variableDebtToken:", reserveData.variableDebtTokenAddress);
            } catch (error) {
                console.log("Not configured in Aave");
            }
        } catch (error) {
            console.log("Error getting token info:", error.message);
        }
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
