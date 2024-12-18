const { ethers } = require("hardhat");
const addresses = require("./addresses");

async function main() {
    console.log("\nStarting flash loan arbitrage test on Sepolia...");

    // Get signer
    const [signer] = await ethers.getSigners();
    console.log("Using account:", signer.address);
    
    console.log("Getting contract instances...\n");

    // Get FlashLoanArbitrage contract
    console.log("Getting FlashLoanArbitrage contract instance...");
    const FLASH_LOAN_ADDRESS = "0x013D9BDe0f96E0C6d3007753aE35a57d98385f62";
    const flashLoanArbitrage = await ethers.getContractAt(
        "FlashLoanArbitrage",
        FLASH_LOAN_ADDRESS
    );
    console.log("Using existing FlashLoanArbitrage contract...");
    console.log("FlashLoanArbitrage at:", FLASH_LOAN_ADDRESS);

    // Set WETH as intermediate token
    console.log("\nSetting WETH as intermediate token...");
    try {
        const setTokenTx = await flashLoanArbitrage.setIntermediateToken(addresses.weth);
        await setTokenTx.wait();
        console.log("WETH set as intermediate token");
    } catch (error) {
        if (!error.message.includes("Transaction reverted: function call to a non-contract")) {
            throw error;
        }
        console.log("WETH is already set as intermediate token");
    }

    // Get USDC contract
    console.log("Getting USDC contract...");
    const usdcContract = await ethers.getContractAt("IERC20", addresses.usdc);
    console.log("Got USDC contract");

    // Get Aave Pool
    console.log("\nGetting Aave Pool address...");
    const pool = await ethers.getContractAt("IPool", addresses.aaveProvider);
    console.log("Aave Pool address:", addresses.aaveProvider);
    console.log("Got Aave Pool contract");

    // Check balances
    const ethBalance = await ethers.provider.getBalance(signer.address);
    const usdcBalance = await usdcContract.balanceOf(signer.address);
    console.log(`\nETH Balance: ${ethers.formatEther(ethBalance)} ETH`);
    console.log(`USDC Balance: ${ethers.formatUnits(usdcBalance, 6)} USDC`);

    // Approve USDC for the contract
    console.log("\nApproving USDC for the contract...");
    const approveTx = await usdcContract.approve(FLASH_LOAN_ADDRESS, ethers.parseUnits("1000", 6));
    await approveTx.wait();
    console.log("USDC approved");

    // Send some USDC to the contract for the premium
    console.log("\nSending USDC to contract for premium...");
    const transferTx = await usdcContract.transfer(FLASH_LOAN_ADDRESS, ethers.parseUnits("10", 6));
    await transferTx.wait();
    console.log("Sent 10 USDC to contract for premium");

    // Execute flash loan
    console.log("\nExecuting flash loan...");
    const flashLoanTx = await flashLoanArbitrage.initiateFlashLoan(
        addresses.usdc,
        ethers.parseUnits("1000", 6)
    );
    await flashLoanTx.wait();
    console.log("Flash loan executed!");

    console.log("\nTest completed successfully!");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("Error executing flash loan:", error);
        process.exit(1);
    });
