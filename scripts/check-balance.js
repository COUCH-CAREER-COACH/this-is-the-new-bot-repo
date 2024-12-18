const { ethers } = require("hardhat");
const addresses = require("./addresses");

async function main() {
    const [signer] = await ethers.getSigners();
    const DAI_ADDRESS = "0xff34b3d4aee8ddcd6f9afffb6fe49bd371b8a357";
    console.log("Checking balances for account:", signer.address);

    // Get DAI contract with full ABI
    const daiAbi = [
        "function balanceOf(address) view returns (uint256)",
        "function decimals() view returns (uint8)",
        "function symbol() view returns (string)",
        "function name() view returns (string)"
    ];

    console.log(`\nChecking DAI at address: ${DAI_ADDRESS}`);
    const daiContract = new ethers.Contract(DAI_ADDRESS, daiAbi, signer);
    
    try {
        const name = await daiContract.name();
        const symbol = await daiContract.symbol();
        const decimals = await daiContract.decimals();
        const balance = await daiContract.balanceOf(signer.address);
        
        console.log(`Token Name: ${name}`);
        console.log(`Token Symbol: ${symbol}`);
        console.log(`Token Decimals: ${decimals}`);
        console.log(`Balance: ${ethers.formatUnits(balance, decimals)} ${symbol}`);
        
    } catch (e) {
        console.log("Error reading token info:", e.message);
    }
    
    // Check ETH balance
    const ethBalance = await ethers.provider.getBalance(signer.address);
    console.log(`\nETH Balance: ${ethers.formatEther(ethBalance)} ETH`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
