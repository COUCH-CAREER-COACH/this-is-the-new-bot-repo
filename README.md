# Arbitrage Bot

This project implements an automated arbitrage bot that monitors and executes profitable trading opportunities across decentralized exchanges. The bot uses flash loans to execute arbitrage trades without requiring initial capital.

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn
- A terminal application

## Setup Instructions

1. Install dependencies:
```shell
npm install
```

2. Make the run script executable:
```shell
chmod +x run-arbitrage.sh
```

## Running the Bot

We've provided a convenient shell script (`run-arbitrage.sh`) to manage all the necessary processes. Here's how to use it:

### 1. Start a Local Blockchain Node

First, start a local Hardhat node in a separate terminal:
```shell
npx hardhat node
```

This will create a local blockchain for testing with pre-funded accounts.

### 2. Deploy the Contracts

In a new terminal window, run:
```shell
./run-arbitrage.sh deploy
```

This command will:
- Deploy mock tokens (WETH, USDC, DAI)
- Deploy mock Uniswap contracts
- Deploy mock Aave contracts
- Deploy the FlashLoanArbitrage contract
- Create initial liquidity pools
- Save all contract addresses to `deployment-addresses.json`

### 3. Set Mock Prices

To create arbitrage opportunities for testing, run:
```shell
./run-arbitrage.sh set-prices
```

This sets up different exchange rates between tokens to create profitable trading opportunities.

### 4. Start the Arbitrage Bot

Finally, start the arbitrage monitoring:
```shell
./run-arbitrage.sh start
```

The bot will continuously monitor token pairs for profitable arbitrage opportunities and execute trades when found.

## Mainnet Deployment

### Prerequisites for Mainnet

1. Set up environment variables in `.env`:
```shell
MAINNET_RPC_URL=your_mainnet_rpc_url
PRIVATE_KEY=your_private_key
MIN_PROFIT_THRESHOLD=0.01  # Minimum profit in ETH
GAS_PRICE_LIMIT=100       # Maximum gas price in gwei
```

2. Ensure you have sufficient ETH for:
   - Contract deployment
   - Flash loan fees
   - Gas costs

### Safety Checks

The bot implements several safety measures:
- Minimum profit threshold accounting for gas costs
- Maximum gas price limit
- Circuit breakers for unusual price movements
- Continuous monitoring of transaction status

### Deploying to Mainnet

1. First, deploy the contracts:
```shell
./run-arbitrage.sh deploy mainnet
```

2. Start monitoring with safety checks:
```shell
./run-arbitrage.sh monitor mainnet
```

3. Check bot status and profits:
```shell
./run-arbitrage.sh status
```

4. Stop the bot safely:
```shell
./run-arbitrage.sh stop
```

### Monitoring and Maintenance

The bot provides real-time monitoring of:
- System resources (CPU, memory usage)
- Profit/loss tracking
- Gas costs
- Transaction success rate
- Price feed health

Monitor the bot's performance using:
```shell
./run-arbitrage.sh status
```

## Testing

Before deploying to mainnet:

1. Test on Sepolia testnet:
```shell
./run-arbitrage.sh test
```

2. Monitor test execution:
```shell
./run-arbitrage.sh monitor sepolia
```

## Command Line Interface (CLI) Guide

For those new to command line interfaces, here's a breakdown of the commands:

1. `chmod +x run-arbitrage.sh`
   - `chmod`: Changes the permissions of a file
   - `+x`: Adds executable permission
   - `run-arbitrage.sh`: The target file

2. `npx hardhat node`
   - `npx`: Runs a package without installing it globally
   - `hardhat`: The development environment we're using
   - `node`: The command to start a local blockchain

3. `./run-arbitrage.sh [command]`
   - `./`: Tells the shell to look in the current directory
   - `run-arbitrage.sh`: The script name
   - `[command]`: One of: `deploy`, `set-prices`, `start`, `monitor`, `status`, `stop`, `test`, or `help`

## Monitoring Output

When the bot is running, you'll see:
- Current token prices and exchange rates
- Detected arbitrage opportunities
- Profit calculations
- Transaction details when trades are executed

To stop any process, press `Ctrl+C` in its terminal window.

## Troubleshooting

1. If you see "Permission denied" when running the script:
   ```shell
   chmod +x run-arbitrage.sh
   ```

2. If deployment fails:
   - Make sure your local blockchain node is running
   - Check that you're using the correct network (localhost)

3. If the bot isn't finding opportunities:
   - Verify that the prices were set correctly
   - Check the deployment addresses in `deployment-addresses.json`
