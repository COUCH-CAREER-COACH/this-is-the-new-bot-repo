const { ethers } = require("hardhat");
const addresses = require("./addresses");

// Aave Faucet ABI
const FAUCET_ABI = [
    "function mint(address token, address to, uint256 amount) external"
];

// Token ABI
const ERC20_ABI = [
    "function balanceOf(address account) external view returns (uint256)",
    "function decimals() external view returns (uint8)",
    "function transfer(address to, uint256 amount) external returns (bool)"
];

async function main() {
    const [signer] = await ethers.getSigners();
    console.log("Using account:", signer.address);

    // Aave Faucet address on Sepolia
    const faucetAddress = "0xC52EA1F19C22E5A3725105BC0CF6531089C6F1C0";
    const faucet = await ethers.getContractAt(FAUCET_ABI, faucetAddress);
    
    // Get DAI contract
    const dai = await ethers.getContractAt(ERC20_ABI, addresses.dai);
    const daiDecimals = await dai.decimals();
    
    // Check initial balance
    const initialDaiBalance = await dai.balanceOf(signer.address);
    console.log(`Initial DAI balance: ${ethers.formatUnits(initialDaiBalance, daiDecimals)}`);

    try {
        // Transfer DAI to the FlashLoanReceiver contract
        const FLASH_LOAN_RECEIVER = "0xd6C82fd0fDc98c734abd44F2fdac86FCF7a2c3ca";
        const transferDaiAmount = ethers.parseUnits("100", daiDecimals);
        
        console.log("\nTransferring 100 DAI to FlashLoanReceiver contract...");
        const transferDaiTx = await dai.transfer(FLASH_LOAN_RECEIVER, transferDaiAmount);
        console.log("DAI transfer tx hash:", transferDaiTx.hash);
        await transferDaiTx.wait();
        
        // Check contract balance
        const contractDaiBalance = await dai.balanceOf(FLASH_LOAN_RECEIVER);
        console.log(`\nFlashLoanReceiver DAI balance: ${ethers.formatUnits(contractDaiBalance, daiDecimals)}`);
        
    } catch (error) {
        console.error("Error:", error.message);
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
