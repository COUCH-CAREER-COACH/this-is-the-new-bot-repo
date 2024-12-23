#!/bin/bash

# Kill any existing Ganache process
pkill -f ganache || true

# Start Ganache with mainnet fork
echo "Starting Ganache..."
ganache \
    --fork.url=https://eth-mainnet.g.alchemy.com/v2/demo \
    --fork.blockNumber=17000000 \
    --miner.defaultGasPrice=20000000000 \
    --chain.chainId=1337 \
    --server.ws=true \
    --wallet.deterministic=true \
    --wallet.totalAccounts=10 \
    --server.port=8545 &

# Wait for Ganache to start
echo "Waiting for Ganache to start..."
until nc -z localhost 8545; do
    sleep 1
done
echo "Ganache is running"

# Run core verification
echo "Running core verification..."
python3 scripts/verify_core_components.py

# Kill Ganache after verification
pkill -f ganache
