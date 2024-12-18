const { ethers } = require("hardhat");

async function main() {
    const txHash = "0xa957d634a6394b8a8a807cc0974df5505b72a1f0084651745a255c1d9ce63ec9";
    console.log("Decoding transaction:", txHash);

    // Get transaction
    const tx = await ethers.provider.getTransaction(txHash);
    const receipt = await ethers.provider.getTransactionReceipt(txHash);
    
    console.log("\nTransaction Details:");
    console.log("From:", tx.from);
    console.log("To:", tx.to);
    console.log("Value:", ethers.formatEther(tx.value), "ETH");
    console.log("Status:", receipt.status === 1 ? "Success" : "Failed");
    
    // Get logs
    console.log("\nTransaction Logs:");
    for (const log of receipt.logs) {
        try {
            // Try to decode Transfer event
            const iface = new ethers.Interface([
                "event Transfer(address indexed from, address indexed to, uint256 value)"
            ]);
            const decoded = iface.parseLog(log);
            if (decoded) {
                console.log("Transfer Event:");
                console.log("  From:", decoded.args[0]);
                console.log("  To:", decoded.args[1]);
                console.log("  Value:", ethers.formatUnits(decoded.args[2], 18));
            }
        } catch (e) {
            // Skip logs that aren't Transfer events
        }
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
