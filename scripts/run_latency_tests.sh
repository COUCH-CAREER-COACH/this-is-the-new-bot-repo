#!/bin/bash

# Exit on error
set -e

# Load environment variables
source .env.test

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Starting latency optimization tests...${NC}\n"

# Ensure directories exist
mkdir -p logs metrics reports/test_results

# Function to check if a service is ready
wait_for_service() {
    local host=$1
    local port=$2
    local service=$3
    local retries=30
    local wait=2

    echo -e "Waiting for $service to be ready..."
    if [ "$service" == "Geth" ]; then
        while true; do
            if curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_syncing","params":[],"id":1}' http://$host:$port | jq -q '.result == false'; then
                echo -e "${GREEN}Geth is synchronized${NC}"
                break
            fi
            if [ "$retries" -eq 0 ]; then
                echo -e "${RED}Geth failed to synchronize in time${NC}"
                return 1
            fi
            retries=$((retries-1))
            sleep $wait
        done
    else
        while ! nc -z $host $port; do
            if [ "$retries" -eq 0 ]; then
                echo -e "${RED}Failed to connect to $service${NC}"
                return 1
            fi
            retries=$((retries-1))
            sleep $wait
        done
        echo -e "${GREEN}$service is ready${NC}"
    fi
}

# Function to check service health
check_service_health() {
    local service=$1
    local url=$2
    local retries=5
    
    while [ $retries -gt 0 ]; do
        if curl -s -f "$url" > /dev/null; then
            echo -e "${GREEN}$service health check passed${NC}"
            return 0
        fi
        retries=$((retries-1))
        sleep 2
    done
    echo -e "${RED}$service health check failed${NC}"
    return 1
}

# Start monitoring stack if not already running
if ! docker-compose -f docker-compose.test.yml ps | grep -q "Up"; then
    echo "Starting monitoring stack..."
    docker-compose -f docker-compose.test.yml up -d
    
    # Wait for core services
    wait_for_service localhost 8545 "Geth"
    wait_for_service localhost 6379 "Redis"
    wait_for_service localhost 9090 "Prometheus"
    wait_for_service localhost 3000 "Grafana"
    
    # Check service health
    check_service_health "Geth" "http://localhost:8545"
    check_service_health "Prometheus" "http://localhost:9090/-/healthy"
    check_service_health "Grafana" "http://localhost:3000/api/health"
fi

echo -e "\n${YELLOW}Running optimization tests...${NC}"

# Run the optimization tests
python3 scripts/run_optimization_tests.py

# Check the exit status
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}Optimization tests completed successfully!${NC}"
    
    # Generate test report
    echo -e "\n${YELLOW}Generating test report...${NC}"
    python3 scripts/generate_test_report.py
    
    # Show summary
    echo -e "\n${GREEN}Test Summary:${NC}"
    echo "- Check the full report at: reports/optimization_report_*.md"
    echo "- View metrics at: http://localhost:3000 (Grafana)"
    echo "- Raw metrics available at: http://localhost:9090 (Prometheus)"
    
    # Check if we meet latency requirements
    avg_latency=$(curl -s "http://localhost:9090/api/v1/query?query=arbitrage:latency:avg_5m" | jq -r '.data.result[0].value[1]')
    if (( $(echo "$avg_latency > 100" | bc -l) )); then
        echo -e "\n${RED}Warning: Average latency ($avg_latency ms) exceeds target (100 ms)${NC}"
        echo "Consider the following optimizations:"
        echo "1. Increase number of Web3 provider connections"
        echo "2. Optimize transaction submission strategy"
        echo "3. Review network conditions and node configuration"
    else
        echo -e "\n${GREEN}Latency requirements met: $avg_latency ms${NC}"
    fi
    
    exit 0
else
    echo -e "\n${RED}Optimization tests failed!${NC}"
    echo "Check the logs for more details:"
    echo "- Application logs: logs/optimization_tests.log"
    echo "- Prometheus logs: logs/prometheus.log"
    echo "- Grafana logs: logs/grafana.log"
    
    # Collect diagnostic information
    echo -e "\n${YELLOW}Collecting diagnostic information...${NC}"
    docker-compose -f docker-compose.test.yml logs > logs/docker-compose.log
    docker stats --no-stream > logs/docker-stats.log
    
    exit 1
fi
