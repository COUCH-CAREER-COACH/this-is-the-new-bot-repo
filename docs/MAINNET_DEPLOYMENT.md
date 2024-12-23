# Mainnet Deployment Guide

This document outlines the complete process for deploying the MEV bot to Ethereum mainnet.

## Prerequisites

1. **Environment Setup**
   - [ ] Ethereum node access (Alchemy/Infura)
   - [ ] Private key with sufficient ETH (minimum 1 ETH recommended)
   - [ ] Flashbots RPC endpoint
   - [ ] Node.js v16+ and Python 3.9+
   - [ ] All dependencies installed: `pip install -r requirements.txt`

2. **Security Requirements**
   - [ ] Hardware wallet for key storage
   - [ ] Secure, isolated deployment environment
   - [ ] VPN connection
   - [ ] SSH key authentication
   - [ ] Firewall configured

3. **Monitoring Setup**
   - [ ] Grafana dashboards configured
   - [ ] Prometheus metrics enabled
   - [ ] Alert system tested
   - [ ] Logging infrastructure ready

## Pre-deployment Checklist

### 1. Configuration Verification
```bash
# Verify mainnet configuration
cat config/mainnet.config.json

# Key parameters to verify:
- Flash loan providers and limits
- Gas price thresholds
- Profit thresholds
- Risk management parameters
- Security settings
```

### 2. Contract Verification
- [ ] Verify all contract addresses in mainnet.config.json
- [ ] Check contract verification on Etherscan
- [ ] Validate ABI files
- [ ] Test contract interactions on testnet

### 3. Security Audit
- [ ] Run security tests: `pytest test/test_mainnet_readiness.py`
- [ ] Verify access controls
- [ ] Check approval limits
- [ ] Review flashbots integration
- [ ] Validate transaction signing

### 4. Risk Management
- [ ] Verify position limits
- [ ] Check circuit breaker parameters
- [ ] Test emergency shutdown
- [ ] Validate profit calculations
- [ ] Review gas estimation

## Deployment Process

### 1. Initial Setup
```bash
# Set environment variables
export MAINNET_RPC_URL="your_rpc_url"
export PRIVATE_KEY="your_private_key"
export FLASHBOTS_RELAY_URL="https://relay.flashbots.net"
export FLASHBOTS_PRIVATE_KEY="your_flashbots_key"

# Verify environment
python3 scripts/test_connections.py
```

### 2. Run Tests
```bash
# Run all tests
pytest test/test_mainnet_readiness.py -v

# Verify specific components
pytest test/test_mainnet_readiness.py -k "test_risk_management"
pytest test/test_mainnet_readiness.py -k "test_security_system"
pytest test/test_mainnet_readiness.py -k "test_monitoring_system"
```

### 3. Gradual Deployment
```bash
# Start deployment script
python3 scripts/deploy_mainnet.py

# Monitor deployment stages:
1. Preflight checks
2. Simulation phase
3. Gradual rollout
```

### 4. Monitoring
```bash
# Check logs
tail -f logs/mainnet_deployment.log

# Monitor metrics
open http://localhost:3000  # Grafana dashboard
```

## Post-deployment Verification

### 1. System Health
- [ ] Verify Web3 connection
- [ ] Check gas price monitoring
- [ ] Validate block monitoring
- [ ] Test emergency shutdown

### 2. Performance Metrics
- [ ] Monitor execution speed
- [ ] Check profit calculations
- [ ] Verify gas estimations
- [ ] Review transaction success rate

### 3. Risk Controls
- [ ] Verify position limits enforced
- [ ] Test circuit breaker
- [ ] Check profit thresholds
- [ ] Monitor exposure limits

## Emergency Procedures

### 1. Emergency Shutdown
```bash
# Immediate shutdown
python3 scripts/emergency_stop.py

# Or use the API endpoint
curl -X POST http://localhost:8080/api/emergency_shutdown
```

### 2. Recovery Steps
1. Stop all active processes
2. Revoke contract approvals
3. Secure funds if necessary
4. Review logs and metrics
5. Implement fixes
6. Run full test suite
7. Gradual restart

### 3. Contact Information
- Technical Lead: [Contact Info]
- Security Team: [Contact Info]
- Infrastructure Support: [Contact Info]

## Monitoring and Maintenance

### 1. Regular Checks
- [ ] Daily performance review
- [ ] Gas price monitoring
- [ ] Profit/loss analysis
- [ ] Risk metrics review

### 2. Updates and Maintenance
- [ ] Weekly code updates
- [ ] Security patches
- [ ] Configuration adjustments
- [ ] Performance optimization

### 3. Backup Procedures
- [ ] Database backups
- [ ] Configuration backups
- [ ] State recovery procedures
- [ ] Rollback plans

## Troubleshooting

### Common Issues

1. **High Gas Prices**
   - Check gas price monitoring
   - Adjust thresholds if needed
   - Review transaction batching

2. **Failed Transactions**
   - Check nonce management
   - Verify gas estimation
   - Review mempool status

3. **Low Profitability**
   - Review profit calculations
   - Check slippage parameters
   - Analyze competition

4. **Network Issues**
   - Verify RPC connection
   - Check node synchronization
   - Monitor network status

## Performance Optimization

### 1. Transaction Optimization
- [ ] Gas optimization
- [ ] Nonce management
- [ ] Flashbots bundle optimization

### 2. Strategy Refinement
- [ ] Profit threshold adjustment
- [ ] Gas price strategy
- [ ] Position sizing

### 3. Risk Management
- [ ] Position limit optimization
- [ ] Circuit breaker tuning
- [ ] Slippage protection

## Compliance and Security

### 1. Security Measures
- [ ] Regular security audits
- [ ] Access control review
- [ ] Key rotation schedule
- [ ] Vulnerability scanning

### 2. Compliance
- [ ] Transaction monitoring
- [ ] Report generation
- [ ] Audit trail maintenance

### 3. Documentation
- [ ] Update deployment logs
- [ ] Maintain incident reports
- [ ] Document configuration changes

## Success Criteria

The deployment is considered successful when:

1. All test cases pass
2. Preflight checks complete successfully
3. Simulation phase shows profitable opportunities
4. Gradual rollout completes without issues
5. Monitoring systems show healthy metrics
6. Risk management systems function properly
7. Security measures are fully operational

## Rollback Plan

If issues are encountered:

1. Execute emergency shutdown
2. Secure any at-risk funds
3. Review logs and metrics
4. Identify root cause
5. Implement fixes
6. Run full test suite
7. Restart gradual deployment

Remember: Safety and security are the top priorities. When in doubt, stop the deployment and review.
