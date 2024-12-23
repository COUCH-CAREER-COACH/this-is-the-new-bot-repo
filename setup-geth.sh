#!/bin/bash

# Create necessary directories
mkdir -p geth-data
mkdir -p geth-metrics

# Set up environment variables
export GETH_DATA_DIR="./geth-data"
export METRICS_DIR="./geth-metrics"

# Pull the latest Geth image
docker pull ethereum/client-go:latest

# Start Geth with optimized parameters
docker-compose -f docker-compose.geth.yml up -d

# Wait for Geth to start
echo "Waiting for Geth to start..."
sleep 10

# Check if Geth is running and syncing
echo "Checking Geth status..."
curl -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_syncing","params":[],"id":1}' http://localhost:8545

echo "
Geth node is running!
RPC endpoint: http://localhost:8545
WebSocket endpoint: ws://localhost:8546

To check sync status:
curl -X POST -H \"Content-Type: application/json\" --data '{\"jsonrpc\":\"2.0\",\"method\":\"eth_syncing\",\"params\":[],\"id\":1}' http://localhost:8545

To check peer count:
curl -X POST -H \"Content-Type: application/json\" --data '{\"jsonrpc\":\"2.0\",\"method\":\"net_peerCount\",\"params\":[],\"id\":1}' http://localhost:8545
"
