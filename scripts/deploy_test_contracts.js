const { ethers } = require("hardhat");

async function main() {
  console.log("Deploying mock contracts...");

  // Deploy MockFlashLoanProvider
  const MockFlashLoanProvider = await ethers.getContractFactory("MockFlashLoanProvider");
  const mockProvider = await MockFlashLoanProvider.deploy();
  await mockProvider.deployed();
  console.log("MockFlashLoanProvider deployed to:", mockProvider.address);

  // Deploy FlashLoanArbitrage
  const FlashLoanArbitrage = await ethers.getContractFactory("FlashLoanArbitrage");
  const flashLoanArbitrage = await FlashLoanArbitrage.deploy();
  await flashLoanArbitrage.deployed();
  console.log("FlashLoanArbitrage deployed to:", flashLoanArbitrage.address);

  // Update test config with deployed addresses
  const fs = require('fs');
  const path = require('path');
  const configPath = path.join(__dirname, '../config/test.local.config.json');
  const config = require(configPath);

  config.flash_loan.providers.aave.pool_address_provider = mockProvider.address;
  config.contracts = {
    ...config.contracts,
    flash_loan_arbitrage: flashLoanArbitrage.address,
    mock_flash_loan_provider: mockProvider.address
  };

  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log("Updated test config with deployed addresses");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
