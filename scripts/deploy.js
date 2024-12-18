const hre = require("hardhat");
const { ethers } = require("hardhat");

async function main() {
    console.log("Starting deployment on Sepolia...");
    const [deployer] = await ethers.getSigners();
    console.log(`Deploying contracts with account: ${deployer.address}`);

    // Sepolia Addresses
    const addresses = {
        aaveProvider: "0x0496275d34753A48320CA58103d5220d394FF77F",
        weth: "0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9", // Sepolia WETH address
        usdc: "0x8267cF9254734C6Eb452a7bb9AAF97B392258b21", // Sepolia USDC address (Aave)
        dai: "0x68194a729C2450ad26072b3D33ADaCbcef39D574", // Sepolia DAI address (Aave)
        uniswapRouter: "0xC532a74256D3Db42D0Bf7a0400fEFDbad7694008"
    };

    // Deploy FlashLoanArbitrage contract
    console.log("Deploying FlashLoanArbitrage contract...");
    const FlashLoanArbitrage = await ethers.getContractFactory("FlashLoanArbitrage");
    const flashLoanArbitrage = await FlashLoanArbitrage.deploy(
        addresses.aaveProvider,
        addresses.uniswapRouter,
        addresses.dai, // Use DAI as the base token instead of WETH
        ethers.parseEther("1000"), // Max flash loan amount (1000 DAI)
        50 // 0.5% minimum profit
    );
    await flashLoanArbitrage.waitForDeployment();
    const contractAddress = await flashLoanArbitrage.getAddress();
    console.log(`FlashLoanArbitrage deployed to: ${contractAddress}`);

    // Get the Aave Pool address
    const aaveProvider = await ethers.getContractAt("IPoolAddressesProvider", addresses.aaveProvider);
    const aavePoolAddress = await aaveProvider.getPool();
    console.log(`Aave Pool address: ${aavePoolAddress}`);

    // Get DAI contract
    const dai = await ethers.getContractAt("IERC20", addresses.dai);

    // Approve tokens
    console.log("\nApproving tokens...");
    await flashLoanArbitrage.approveToken(addresses.dai, aavePoolAddress);
    console.log("DAI approved for Aave Pool");
    await flashLoanArbitrage.approveToken(addresses.dai, addresses.uniswapRouter);
    console.log("DAI approved for Uniswap Router");

    // Set DAI as intermediate token
    await flashLoanArbitrage.setIntermediateToken(addresses.dai);
    console.log("Set DAI as intermediate token");

    console.log("\nDeployment Summary:");
    console.log("------------------");
    console.log(`FlashLoanArbitrage: ${contractAddress}`);
    console.log(`AAVE Pool Provider: ${addresses.aaveProvider}`);
    console.log(`AAVE Pool: ${aavePoolAddress}`);
    console.log(`WETH: ${addresses.weth}`);
    console.log(`USDC: ${addresses.usdc}`);
    console.log(`DAI: ${addresses.dai}`);
    console.log(`Uniswap Router: ${addresses.uniswapRouter}`);

    return {
        flashLoanArbitrage: contractAddress,
        aaveProvider: addresses.aaveProvider,
        aavePool: aavePoolAddress,
        weth: addresses.weth,
        usdc: addresses.usdc,
        dai: addresses.dai,
        uniswapRouter: addresses.uniswapRouter
    };
}

main()
    .then((addresses) => {
        console.log("\nDeployment completed successfully!");
        // Save addresses to file
        const fs = require("fs");
        fs.writeFileSync(
            "deployment-addresses.json",
            JSON.stringify(addresses, null, 2)
        );
        process.exit(0);
    })
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
