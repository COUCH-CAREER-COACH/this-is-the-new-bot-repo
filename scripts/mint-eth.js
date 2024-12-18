const { ethers } = require("hardhat");

async function main() {
    const [deployer] = await ethers.getSigners();
    console.log(`Deployer address: ${deployer.address}`);
    console.log(`Initial balance: ${ethers.formatEther(await ethers.provider.getBalance(deployer.address))} ETH`);

    // Send 1000 ETH to the deployer
    const newBalance = "0x" + ethers.parseEther("1000000").toString(16);
    await ethers.provider.send("hardhat_setBalance", [
        deployer.address,
        newBalance
    ]);

    console.log(`New balance: ${ethers.formatEther(await ethers.provider.getBalance(deployer.address))} ETH`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
