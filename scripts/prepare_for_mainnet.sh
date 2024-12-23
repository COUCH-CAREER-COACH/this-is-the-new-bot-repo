#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        print_status "$GREEN" "✓ Success: $1"
    else
        print_status "$RED" "✗ Failed: $1"
        exit 1
    fi
}

# Function to prompt for confirmation
confirm() {
    read -p "$1 (yes/no) " response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Print banner
echo "================================================="
echo "          MEV Bot Mainnet Preparation             "
echo "================================================="

# Check environment variables
print_status "$YELLOW" "\nChecking environment variables..."
required_vars=(
    "MAINNET_RPC_URL"
    "PRIVATE_KEY"
    "FLASHBOTS_PRIVATE_KEY"
    "ETHERSCAN_API_KEY"
    "SAFE_ADDRESS"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        print_status "$RED" "✗ Missing required environment variable: $var"
        exit 1
    fi
done
check_status "Environment variables verified"

# Create necessary directories
print_status "$YELLOW" "\nCreating necessary directories..."
mkdir -p logs metrics data reports
check_status "Directory creation"

# Install dependencies
print_status "$YELLOW" "\nInstalling/updating dependencies..."
pip install -r requirements.txt
check_status "Dependencies installation"

# Run tests
print_status "$YELLOW" "\nRunning test suite..."
pytest test/test_mainnet_readiness.py -v
check_status "Test suite execution"

# Verify mainnet readiness
print_status "$YELLOW" "\nVerifying mainnet readiness..."
python3 scripts/verify_mainnet_readiness.py
status=$?
if [ $status -eq 0 ]; then
    print_status "$GREEN" "✓ Mainnet verification passed"
elif [ $status -eq 2 ]; then
    print_status "$YELLOW" "⚠ Mainnet verification passed with warnings"
    if ! confirm "Continue despite warnings?"; then
        exit 1
    fi
else
    print_status "$RED" "✗ Mainnet verification failed"
    exit 1
fi

# Check contract deployments
print_status "$YELLOW" "\nVerifying contract deployments..."
python3 scripts/test_connections.py
check_status "Contract verification"

# Test emergency stop
print_status "$YELLOW" "\nTesting emergency stop functionality..."
python3 scripts/emergency_stop.py --force
check_status "Emergency stop test"

# Backup configuration
print_status "$YELLOW" "\nBacking up configuration..."
timestamp=$(date +%Y%m%d_%H%M%S)
mkdir -p backups
cp config/mainnet.config.json "backups/mainnet.config.${timestamp}.json"
cp .env "backups/.env.${timestamp}"
check_status "Configuration backup"

# Security checks
print_status "$YELLOW" "\nRunning security checks..."

# Check gas settings
gas_price=$(python3 -c "
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('$MAINNET_RPC_URL'))
print(w3.eth.gas_price)
")
max_gas=$(python3 -c "
import json
with open('config/mainnet.config.json') as f:
    config = json.load(f)
print(config['max_gas_price'])
")

if [ "$gas_price" -gt "$max_gas" ]; then
    print_status "$RED" "✗ Current gas price exceeds configured maximum"
    exit 1
fi
check_status "Gas price verification"

# Verify balance
balance=$(python3 -c "
from web3 import Web3
from eth_account import Account
w3 = Web3(Web3.HTTPProvider('$MAINNET_RPC_URL'))
account = Account.from_key('$PRIVATE_KEY')
print(w3.eth.get_balance(account.address))
")
min_balance=1000000000000000000  # 1 ETH in wei

if [ "$balance" -lt "$min_balance" ]; then
    print_status "$RED" "✗ Insufficient ETH balance"
    exit 1
fi
check_status "Balance verification"

# Final confirmation
echo
print_status "$YELLOW" "Pre-deployment checklist complete!"
echo
echo "Summary:"
echo "- All tests passed"
echo "- Mainnet verification completed"
echo "- Contracts verified"
echo "- Emergency stop tested"
echo "- Configuration backed up"
echo "- Security checks passed"
echo
echo "Next steps:"
echo "1. Review the verification report in reports/"
echo "2. Monitor system metrics in metrics/"
echo "3. Keep emergency_stop.py readily available"
echo "4. Run deploy_mainnet.py to start deployment"
echo

if confirm "Ready to proceed with mainnet deployment?"; then
    print_status "$YELLOW" "\nStarting mainnet deployment..."
    python3 scripts/deploy_mainnet.py
    check_status "Mainnet deployment"
    
    print_status "$GREEN" "\nDeployment complete! Monitor the bot at:"
    echo "- Logs: tail -f logs/mainnet_deployment.log"
    echo "- Metrics: http://localhost:3000 (Grafana)"
    echo "- Alerts: Check monitoring system"
else
    print_status "$YELLOW" "\nDeployment cancelled. Review and try again when ready."
fi
