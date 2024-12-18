require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

const ALCHEMY_API_KEY = process.env.ALCHEMY_API_KEY || "0CyBce3JTmhrkJF1bLUTSKJLQVxTmAEx";
const PRIVATE_KEY = process.env.PRIVATE_KEY || "b0d30e93fd18335b57265054ee6102a9034a70ed1c20ca5a13b48cd7b60e6266";

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.19",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      viaIR: true,
    },
  },
  networks: {
    hardhat: {
      allowUnlimitedContractSize: true,
      chainId: 1337,
      mining: {
        auto: true,
        interval: 0
      },
      forking: {
        url: `https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`,
        enabled: true,
        blockNumber: 18791993
      }
    },
    mainnet: {
      url: `https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`,
      wsUrl: `wss://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`,
      accounts: [PRIVATE_KEY],
      chainId: 1
    }
  },
  mocha: {
    timeout: 40000,
  }
};
