const { ethers } = require("hardhat");
const addresses = require("./addresses");

// Flash loan contract ABI - only the functions we need
const AAVE_POOL_ABI = [
    "function flashLoanSimple(address receiverAddress, address asset, uint256 amount, bytes calldata params, uint16 referralCode) external",
    "function FLASHLOAN_PREMIUM_TOTAL() external view returns (uint128)",
];

// Token ABI for checking balance
const ERC20_ABI = [
    "function balanceOf(address account) external view returns (uint256)",
    "function decimals() external view returns (uint8)",
    "function approve(address spender, uint256 amount) external returns (bool)",
    "function transfer(address to, uint256 amount) external returns (bool)",
];

// FlashLoanReceiver ABI
const FLASH_RECEIVER_ABI = [
    "function approveToken(address token, address spender, uint256 amount) external",
];

async function main() {
    const [signer] = await ethers.getSigners();
    console.log("Using account:", signer.address);

    // Connect to contracts
    const pool = await ethers.getContractAt(AAVE_POOL_ABI, addresses.aavePool);
    const dai = await ethers.getContractAt(ERC20_ABI, addresses.dai);
    const decimals = await dai.decimals();
    
    // Check flash loan fee
    const flashLoanPremium = await pool.FLASHLOAN_PREMIUM_TOTAL();
    console.log(`Flash Loan Premium: ${flashLoanPremium} basis points`);

    // Flash loan receiver contract address
    const FLASH_LOAN_RECEIVER = "0xf7dFe8310687846F9Cd16bb4a4C341F2f4BEe096";
    const flashReceiver = await ethers.getContractAt(FLASH_RECEIVER_ABI, FLASH_LOAN_RECEIVER);

    // First, transfer some DAI to the receiver contract to cover the premium
    const transferAmount = ethers.parseUnits("100", decimals); // Transfer 100 DAI to cover fees
    console.log("\nTransferring 100 DAI to FlashLoanReceiver contract...");
    const transferTx = await dai.transfer(FLASH_LOAN_RECEIVER, transferAmount);
    console.log("Transfer tx hash:", transferTx.hash);
    await transferTx.wait();

    // Approve the pool to spend DAI from the receiver contract
    console.log("\nApproving DAI spending...");
    const approveTx = await flashReceiver.approveToken(
        addresses.dai,
        addresses.aavePool,
        ethers.parseUnits("10000", decimals) // Approve more than needed to be safe
    );
    console.log("Approve tx hash:", approveTx.hash);
    await approveTx.wait();

    // Check DAI balances
    const receiverBalance = await dai.balanceOf(FLASH_LOAN_RECEIVER);
    console.log(`\nFlashLoanReceiver DAI Balance: ${ethers.formatUnits(receiverBalance, decimals)}`);

    // Flash loan parameters
    const flashLoanAmount = ethers.parseUnits("1000", decimals); // Borrow 1000 DAI
    
    try {
        // Execute flash loan
        console.log(`\nRequesting flash loan of 1000 DAI...`);
        const tx = await pool.flashLoanSimple(
            FLASH_LOAN_RECEIVER,  // receiver address - our deployed FlashLoanReceiver contract
            addresses.dai,       // asset to borrow
            flashLoanAmount,    // amount to borrow
            "0x",              // params - empty in this case
            0                  // referral code - 0 for no referral
        );
        
        console.log("Flash loan tx hash:", tx.hash);
        await tx.wait();
        
        // Check DAI balance after
        const balanceAfter = await dai.balanceOf(FLASH_LOAN_RECEIVER);
        console.log(`FlashLoanReceiver DAI Balance After: ${ethers.formatUnits(balanceAfter, decimals)}`);
        
    } catch (error) {
        console.error("Error executing flash loan:", error.message);
        if (error.data) {
            console.error("Error data:", error.data);
        }
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
