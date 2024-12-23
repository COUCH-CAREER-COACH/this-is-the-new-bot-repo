#!/bin/bash

# Create necessary directories
mkdir -p data/ganache
mkdir -p logs

# Kill any existing Ganache instances
pkill -f ganache || true

# Wait for ports to be released
sleep 2

# Start Ganache with mainnet-like settings
ganache \
  --port 8545 \
  --server.ws true \
  --server.ws.port 8546 \
  --chain.chainId 1 \
  --chain.networkId 1 \
  --chain.vmErrorsOnRPCResponse true \
  --wallet.totalAccounts 10 \
  --wallet.defaultBalance 1000 \
  --miner.blockTime 12 \
  --miner.defaultGasPrice 50000000000 \
  --miner.blockGasLimit 12000000 \
  --database.dbPath "./data/ganache" \
  --logging.debug true \
  --chain.allowUnlimitedContractSize true \
  --chain.asyncRequestProcessing true \
  --miner.instamine full \
  --wallet.deterministic true \
  --wallet.mnemonic "test test test test test test test test test test test junk" \
  > ./logs/ganache.log 2>&1 &

# Wait for Ganache to start
echo "Starting Ganache..."
sleep 5

# Verify Ganache is running
if ! nc -z localhost 8545; then
    echo "Error: Ganache HTTP server not running"
    exit 1
fi

if ! nc -z localhost 8546; then
    echo "Error: Ganache WebSocket server not running"
    exit 1
fi

echo "Ganache is running with mainnet-like settings"
