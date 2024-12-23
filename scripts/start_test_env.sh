#!/bin/bash

# Kill any existing Ganache instances
pkill -f ganache

# Wait for ports to be released
sleep 2

# Start Ganache with specific parameters
ganache \
  --fork.url http://localhost:8545 \
  --fork.blockNumber 17000000 \
  --server.ws true \
  --server.port 8545 \
  --server.host 0.0.0.0 \
  --chain.chainId 1 \
  --wallet.totalAccounts 10 \
  --wallet.defaultBalance 10000 \
  --miner.blockGasLimit 30000000 \
  --miner.defaultGasPrice 50000000000 \
  --wallet.deterministic true \
  --database.dbPath ./ganache_db \
  --logging.debug true \
  --websocket.enabled true \
  --websocket.port 8546 \
  --chain.allowUnlimitedContractSize false \
  --fork.requestsPerSecond 50 \
  --chain.vmErrorsOnRPCResponse true \
  --chain.asyncRequestProcessing true \
  --miner.instamine strict &

# Wait for Ganache to start
sleep 5

# Run the tests
python -m pytest test/test_latency_optimization.py -v

# Cleanup
pkill -f ganache
rm -rf ganache_db
