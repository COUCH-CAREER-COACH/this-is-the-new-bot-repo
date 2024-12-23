#!/bin/bash
set -e

# Function to wait for a service
wait_for_service() {
    local host="$1"
    local port="$2"
    local service="$3"
    local timeout=30
    local elapsed=0

    echo "Waiting for $service at $host:$port..."
    while ! nc -z "$host" "$port"; do
        if [ "$elapsed" -ge "$timeout" ]; then
            echo "Timeout waiting for $service"
            exit 1
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    echo "$service is up!"
}

# Create required directories
mkdir -p logs reports metrics tmp
chmod -R 777 logs reports metrics tmp

# Wait for required services
wait_for_service geth-node 8545 "Geth HTTP"
wait_for_service geth-node 8546 "Geth WebSocket"
wait_for_service redis 6379 "Redis"
wait_for_service prometheus 9090 "Prometheus"

# Initialize application
echo "Initializing application..."

# Execute the main command
exec "$@"
