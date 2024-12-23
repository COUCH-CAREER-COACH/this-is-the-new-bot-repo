# Ethereum Node Setup Guide

This guide explains how to set up and run your own Ethereum node with monitoring capabilities.

## System Requirements

- CPU: 8+ cores
- RAM: 32GB minimum
- Storage: 2TB+ NVMe SSD
- Network: High bandwidth, low latency connection

## Installation & Setup

1. **Clone and prepare the environment**:
```bash
# Create data directories
mkdir -p geth-data
mkdir -p grafana/dashboards
chmod +x setup-geth.sh
```

2. **Configure environment**:
Create a `.env` file with your settings:
```bash
# Node configuration
WEB3_PROVIDER_URI=http://localhost:8545
WS_PROVIDER_URI=ws://localhost:8546

# Monitoring
GRAFANA_ADMIN_PASSWORD=your_secure_password_here
```

3. **Start the node**:
```bash
./setup-geth.sh
```

4. **Access monitoring dashboards**:
- Grafana: http://localhost:3000 (default credentials: admin/your_secure_password_here)
- Prometheus: http://localhost:9090

## Monitoring Features

The setup includes:
- Geth metrics (block height, peer count, pending transactions)
- System metrics (CPU, memory, disk usage)
- Network metrics (bandwidth, latency)
- Transaction pool monitoring
- P2P network statistics

## Performance Optimization

The Geth node is configured with optimized settings for MEV/arbitrage:

- Large transaction pool (`--txpool.globalslots=20000`)
- High peer count (`--maxpeers=100`)
- Aggressive caching (`--cache=8192`)
- Archive mode for full historical data
- WebSocket enabled for real-time updates
- Metrics enabled for monitoring
- Debug APIs enabled for detailed inspection

## Maintenance

1. **Check node status**:
```bash
# Check sync status
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_syncing","params":[],"id":1}' \
  http://localhost:8545

# Check peer count
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}' \
  http://localhost:8545
```

2. **Update node**:
```bash
docker-compose -f docker-compose.geth.yml pull
docker-compose -f docker-compose.geth.yml up -d
```

3. **View logs**:
```bash
docker-compose -f docker-compose.geth.yml logs -f geth
```

## Security Recommendations

1. **Firewall Configuration**:
```bash
# Allow only necessary ports
sudo ufw allow 30303/tcp  # P2P
sudo ufw allow 30303/udp  # P2P
sudo ufw allow 8545/tcp   # RPC (restrict to your IP)
sudo ufw allow 8546/tcp   # WebSocket (restrict to your IP)
```

2. **SSL/TLS Setup**:
Consider setting up SSL/TLS for RPC and WebSocket connections using a reverse proxy like nginx.

3. **Access Control**:
- Use strong passwords for Grafana
- Restrict RPC/WS access to your bot's IP only
- Regularly update all components

## Troubleshooting

1. **Node not syncing**:
- Check peer connections
- Verify network connectivity
- Ensure sufficient disk space

2. **High resource usage**:
- Monitor through Grafana dashboard
- Adjust cache and memory settings if needed
- Consider reducing peer count

3. **Connection issues**:
- Check firewall settings
- Verify port forwarding
- Ensure correct RPC/WS endpoints

## Integration with MEV Bot

Update your bot's configuration to use your local node:

1. Update `.env`:
```bash
WEB3_PROVIDER_URI=http://localhost:8545
WS_PROVIDER_URI=ws://localhost:8546
```

2. Restart your bot to use the local node.

## Monitoring Best Practices

1. Set up alerts in Grafana for:
- Node disconnections
- Sync issues
- High resource usage
- Large pending transaction pool
- Network peer count drops

2. Regular health checks:
- Monitor block height vs network
- Check peer count stability
- Review system resource usage
- Verify transaction processing

Remember to regularly check the Grafana dashboard for node performance and health metrics.
