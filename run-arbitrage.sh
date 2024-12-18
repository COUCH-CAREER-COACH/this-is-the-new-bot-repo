#!/bin/bash

# Load environment variables if present
if [ -f .env ]; then
    source .env
fi

# Function to display usage instructions
show_usage() {
    echo "Arbitrage Bot Control Script"
    echo "Usage:"
    echo "  ./run-arbitrage.sh [command] [network]"
    echo ""
    echo "Commands:"
    echo "  deploy     - Deploy all contracts and save addresses"
    echo "  monitor    - Start the arbitrage monitoring"
    echo "  test       - Run on testnet (Sepolia)"
    echo "  mainnet    - Run on mainnet with safety checks"
    echo "  stop       - Stop the arbitrage monitoring"
    echo "  status     - Check bot status and profits"
    echo "  help       - Show this help message"
    echo ""
    echo "Networks:"
    echo "  sepolia    - Sepolia testnet"
    echo "  mainnet    - Ethereum mainnet (requires confirmation)"
}

# Function to check prerequisites
check_prerequisites() {
    # Check if node and npm are installed
    if ! command -v node > /dev/null; then
        echo "Error: NodeJS is not installed"
        exit 1
    fi

    # Check if required environment variables are set
    if [ "$1" == "mainnet" ]; then
        if [ -z "$MAINNET_RPC_URL" ]; then
            echo "Error: MAINNET_RPC_URL is not set"
            exit 1
        fi
        if [ -z "$PRIVATE_KEY" ]; then
            echo "Error: PRIVATE_KEY is not set"
            exit 1
        fi
    fi
}

# Function to monitor bot process
monitor_bot() {
    local network=$1
    local pid_file="bot.pid"
    
    # Start the bot and save its PID
    npx hardhat run scripts/execute-arbitrage.js --network $network &
    echo $! > $pid_file
    
    # Monitor system resources
    while true; do
        if [ ! -f $pid_file ]; then
            echo "Bot process not found!"
            exit 1
        fi
        
        pid=$(cat $pid_file)
        if ! ps -p $pid > /dev/null; then
            echo "Bot process died unexpectedly!"
            exit 1
        fi
        
        # Log system stats
        echo "$(date) - Memory: $(ps -o %mem -p $pid | tail -1)% CPU: $(ps -o %cpu -p $pid | tail -1)%"
        sleep 60
    done
}

# Function to stop the bot
stop_bot() {
    if [ -f bot.pid ]; then
        pid=$(cat bot.pid)
        kill $pid 2>/dev/null || true
        rm bot.pid
        echo "Bot stopped"
    else
        echo "No running bot found"
    fi
}

# Function to check bot status
check_status() {
    if [ -f bot.pid ]; then
        pid=$(cat bot.pid)
        if ps -p $pid > /dev/null; then
            echo "Bot is running (PID: $pid)"
            # Get profit statistics from the logs
            echo "Recent Activity:"
            tail -n 10 arbitrage.log 2>/dev/null || echo "No recent activity"
        else
            echo "Bot process not found but PID file exists"
            rm bot.pid
        fi
    else
        echo "Bot is not running"
    fi
}

# Main script logic
case "$1" in
    "deploy")
        network=${2:-sepolia}
        check_prerequisites $network
        echo "Deploying contracts to $network..."
        npx hardhat run scripts/deploy.js --network $network
        ;;
    "monitor")
        network=${2:-sepolia}
        check_prerequisites $network
        echo "Starting arbitrage monitoring on $network..."
        monitor_bot $network
        ;;
    "test")
        check_prerequisites "sepolia"
        echo "Running on Sepolia testnet..."
        npx hardhat run scripts/execute-arbitrage.js --network sepolia
        ;;
    "mainnet")
        echo "WARNING: You are about to run the bot on mainnet!"
        echo "This will use real funds. Are you sure? (yes/no)"
        read confirmation
        if [ "$confirmation" == "yes" ]; then
            check_prerequisites "mainnet"
            echo "Starting bot on mainnet..."
            monitor_bot mainnet
        else
            echo "Mainnet deployment cancelled"
        fi
        ;;
    "stop")
        stop_bot
        ;;
    "status")
        check_status
        ;;
    "help"|"")
        show_usage
        ;;
    *)
        echo "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
