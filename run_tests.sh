#!/bin/bash

# Exit on error
set -e

echo "Starting comprehensive test suite..."

# Ensure we're in virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Create test directories if they don't exist
mkdir -p reports/test_results
mkdir -p reports/coverage
mkdir -p logs/test

# Start local Ethereum node for testing
echo "Starting local Ethereum node..."
if ! pgrep -f "ganache" > /dev/null; then
    ganache \
        --fork https://eth-mainnet.alchemyapi.io/v2/your-api-key \
        --fork.blockNumber 17000000 \
        --chain.chainId 1 \
        --wallet.totalAccounts 5 \
        --wallet.defaultBalance 10000 \
        --miner.blockGasLimit 12000000 \
        --miner.defaultGasPrice 50000000000 \
        --server.ws true \
        --database.dbPath test/chain_db \
        > logs/test/ganache.log 2>&1 &
    
    # Wait for node to start
    sleep 5
fi

# Function to run a test category
run_test_category() {
    local category=$1
    local markers=$2
    echo "Running $category tests..."
    
    pytest \
        -v \
        --capture=no \
        -m "$markers" \
        --html=reports/test_results/${category}_report.html \
        --self-contained-html \
        --cov=src \
        --cov-report=html:reports/coverage/${category}_coverage \
        test/ \
        || return 1
}

# Run tests in specific order
echo "Running test suite in order of dependency..."

# 1. Basic unit tests
run_test_category "unit" "not integration and not mainnet" || {
    echo "❌ Unit tests failed"
    exit 1
}

# 2. Integration tests
run_test_category "integration" "integration and not mainnet" || {
    echo "❌ Integration tests failed"
    exit 1
}

# 3. Gas optimization tests
run_test_category "gas" "gas" || {
    echo "❌ Gas optimization tests failed"
    exit 1
}

# 4. Latency optimization tests
run_test_category "latency" "latency" || {
    echo "❌ Latency optimization tests failed"
    exit 1
}

# 5. Position optimization tests
run_test_category "position" "position" || {
    echo "❌ Position optimization tests failed"
    exit 1
}

# 6. Risk management tests
run_test_category "risk" "risk" || {
    echo "❌ Risk management tests failed"
    exit 1
}

# 7. Security tests
run_test_category "security" "security" || {
    echo "❌ Security tests failed"
    exit 1
}

# 8. Mainnet simulation tests
run_test_category "mainnet" "mainnet" || {
    echo "❌ Mainnet simulation tests failed"
    exit 1
}

# Generate combined coverage report
echo "Generating combined coverage report..."
coverage combine
coverage html -d reports/coverage/combined
coverage report

# Clean up
echo "Cleaning up..."
pkill -f "ganache" || true

# Check coverage threshold
coverage report --fail-under=80 || {
    echo "❌ Coverage below threshold"
    exit 1
}

echo "✅ All tests completed successfully!"

# Generate test summary
echo "Generating test summary..."
cat > reports/test_results/summary.md << EOF
# Test Suite Summary

## Test Categories
1. Unit Tests
2. Integration Tests
3. Gas Optimization Tests
4. Latency Optimization Tests
5. Position Optimization Tests
6. Risk Management Tests
7. Security Tests
8. Mainnet Simulation Tests

## Coverage Report
$(coverage report)

## Test Reports
- Unit Test Report: [View](unit_report.html)
- Integration Test Report: [View](integration_report.html)
- Gas Optimization Report: [View](gas_report.html)
- Latency Optimization Report: [View](latency_report.html)
- Position Optimization Report: [View](position_report.html)
- Risk Management Report: [View](risk_report.html)
- Security Report: [View](security_report.html)
- Mainnet Simulation Report: [View](mainnet_report.html)

## Coverage Reports
- Combined Coverage Report: [View](../coverage/combined/index.html)
- Individual Coverage Reports:
  - Unit Tests: [View](../coverage/unit_coverage/index.html)
  - Integration Tests: [View](../coverage/integration_coverage/index.html)
  - Gas Optimization: [View](../coverage/gas_coverage/index.html)
  - Latency Optimization: [View](../coverage/latency_coverage/index.html)
  - Position Optimization: [View](../coverage/position_coverage/index.html)
  - Risk Management: [View](../coverage/risk_coverage/index.html)
  - Security: [View](../coverage/security_coverage/index.html)
  - Mainnet Simulation: [View](../coverage/mainnet_coverage/index.html)
EOF

echo "Test summary generated at reports/test_results/summary.md"
