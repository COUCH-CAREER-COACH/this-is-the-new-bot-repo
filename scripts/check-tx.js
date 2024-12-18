const { ethers } = require("hardhat");
const addresses = require("./addresses");

async function main() {
    const [signer] = await ethers.getSigners();
    
    console.log("Checking DAI transfers...");
    console.log("DAI address:", addresses.dai);
    console.log("Signer address:", signer.address);

    // Get DAI contract
    const daiAbi = [
        "function balanceOf(address) view returns (uint256)",
        "event Transfer(address indexed from, address indexed to, uint256 value)"
    ];
    const daiContract = new ethers.Contract(addresses.dai, daiAbi, signer);
    
    // Get recent transfer events
    const filter = daiContract.filters.Transfer();  // Look for all transfers
    const currentBlock = await ethers.provider.getBlockNumber();
    const fromBlock = currentBlock - 10; // Look back 10 blocks
    
    console.log(`\nSearching for transfers from block ${fromBlock} to ${currentBlock}...`);
    
    const events = await daiContract.queryFilter(filter, fromBlock);
    console.log(`Found ${events.length} transfer events\n`);
    
    for (const event of events) {
        const block = await event.getBlock();
        console.log(`Block ${event.blockNumber} (${new Date(block.timestamp * 1000).toLocaleString()})`);
        console.log(`From: ${event.args[0]}`);
        console.log(`To: ${event.args[1]}`);
        console.log(`Amount: ${ethers.formatUnits(event.args[2], 18)} DAI`);
        console.log(`Transaction: ${event.transactionHash}\n`);
    }

    // Check balance again
    const balance = await daiContract.balanceOf(signer.address);
    console.log(`Current DAI balance: ${ethers.formatUnits(balance, 18)} DAI`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
