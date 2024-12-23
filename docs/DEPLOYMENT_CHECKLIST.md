# Updated Mainnet Deployment Checklist

## Pre-Deployment Verification

### 1. Geth Node Setup
- [ ] Geth node fully synced with mainnet
- [ ] Correct flags enabled in docker-compose.geth.yml:
  - HTTP RPC (--http)
  - WebSocket (--ws)
  - Required APIs (eth,net,web3,txpool,debug,admin)
  - Archive mode (--gcmode=archive)
- [ ] Node metrics exposed on port 6060
- [ ] Proper resource limits configured (CPU/Memory)
- [ ] Data persistence configured correctly
- [ ] Network connectivity verified

### 2. Configuration Verification
- [ ] mainnet.config.json updated with correct Geth node URLs:
  - RPC URL: http://geth:8545
  - WebSocket URL: ws://geth:8546
- [ ] Chain ID set to 1 (mainnet)
- [ ] Contract addresses verified on mainnet
- [ ] Gas price strategy and limits configured
- [ ] Strategy parameters optimized for mainnet
- [ ] Flash loan provider settings verified

### 3. Monitoring Setup
- [ ] Grafana dashboard operational with panels:
  - Trading Activity
  - Current Profit Ratio
  - Gas Price
  - Execution Time
- [ ] Prometheus data source configured correctly
- [ ] Alert rules active for:
  - High gas price (>200 Gwei)
  - Low profitability (<0.5%)
  - High failure rate (>30%)
  - Bot health
  - High latency (>2s)
  - Low liquidity
  - Resource usage (CPU/Memory)
  - Redis connection
  - Geth sync status
  - Block delay
- [ ] Alert notifications configured (Telegram)
- [ ] Metrics retention period set (15d)
- [ ] Dashboard refresh rate configured (5s)

### 4. Security Measures
- [ ] Circuit breakers configured:
  - Gas price limits
  - Position size limits
  - Profit thresholds
  - Network conditions
- [ ] Emergency withdrawal mechanism tested
  - Safe address configured
  - Threshold amounts set
- [ ] Private keys secured
- [ ] Access controls implemented
- [ ] Rate limiting configured
- [ ] Slippage protection active

### 5. Performance Optimization
- [ ] Cache settings optimized:
  - Max age: 60s
  - Max size: 100MB
- [ ] Concurrent tasks limit set (10)
- [ ] Batch size configured (100)
- [ ] Mempool scan interval optimized (100ms)
- [ ] WebSocket reconnection strategy configured
- [ ] Resource limits properly set in docker-compose

### 6. Strategy Configuration
- [ ] Sandwich strategy parameters verified:
  - Profit thresholds
  - Position limits
  - Target pairs
  - Price impact limits
- [ ] Frontrunning strategy configured
- [ ] JIT liquidity parameters set
- [ ] Risk management limits implemented
- [ ] Gas optimization settings verified

## Deployment Process

### 1. Pre-deployment Tests
```bash
# Verify node connection
python scripts/verify_mainnet_readiness.py

# Check configuration
python scripts/verify_yaml_config.py

# Verify core components
python scripts/verify_core_components.py

# Run security checks
python scripts/verify_security.py
```

### 2. Deployment Steps
```bash
# Start Geth node
docker-compose -f docker-compose.geth.yml up -d

# Wait for sync
./scripts/verify_bot.sh

# Deploy monitoring
docker-compose up -d prometheus grafana

# Start bot with minimal positions
docker-compose up -d mev-bot
```

### 3. Post-deployment Verification
```bash
# Check bot health
curl http://localhost:8000/health

# Verify metrics
curl http://localhost:8080/metrics

# Monitor logs
docker-compose logs -f mev-bot
```

## Monitoring Checklist

### 1. Grafana Verification
- [ ] Access Grafana UI (http://localhost:3000)
- [ ] Verify data source connection
- [ ] Check all dashboard panels are updating
- [ ] Test alert notifications
- [ ] Verify metrics collection
- [ ] Check dashboard permissions

### 2. Prometheus Verification
- [ ] Metrics being collected
- [ ] Alert rules loaded
- [ ] Storage retention configured
- [ ] Resource usage within limits
- [ ] Target scraping successful

### 3. Alert System
- [ ] Telegram notifications working
- [ ] Alert thresholds appropriate
- [ ] Alert routing configured
- [ ] Escalation paths defined
- [ ] Alert documentation updated

## Emergency Procedures

### 1. Circuit Breaker Triggers
- [ ] Gas price exceeds 300 Gwei
- [ ] Profit ratio below 0.5%
- [ ] Failed transaction rate above 30%
- [ ] Block delay above 60 seconds
- [ ] Memory usage above 1GB
- [ ] CPU usage above 80%

### 2. Emergency Contacts
- Technical Lead: [Contact Info]
- Operations Lead: [Contact Info]
- Security Team: [Contact Info]

### 3. Recovery Procedures
- [ ] Emergency shutdown procedure documented
- [ ] Fund recovery process tested
- [ ] Incident response plan updated
- [ ] Backup restoration process verified
- [ ] Communication templates prepared

## Sign-off Requirements

- [ ] Technical Lead Approval
- [ ] Operations Lead Approval
- [ ] Security Team Approval
- [ ] Monitoring Team Approval

Date: ________________
Approved By: ________________
Signature: ________________

Note: This checklist must be completed and signed off before proceeding with mainnet deployment. Each item should be verified and documented. Any deviations must be approved and documented.
