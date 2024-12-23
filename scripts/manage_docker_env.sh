#!/bin/bash
set -e

# Function to check if a container is healthy
check_health() {
    local container=$1
    local max_attempts=30
    local attempt=1
    
    echo "Checking health of $container..."
    while [ $attempt -le $max_attempts ]; do
        if docker inspect --format='{{.State.Health.Status}}' $container 2>/dev/null | grep -q "healthy"; then
            echo "$container is healthy!"
            return 0
        fi
        echo "Attempt $attempt/$max_attempts: $container not healthy yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "Error: $container failed to become healthy"
    return 1
}

# Function to start the environment
start_env() {
    echo "Starting Docker environment..."
    
    # Ensure we're using .env.test
    if [ ! -f .env.test ]; then
        echo "Error: .env.test file not found!"
        exit 1
    fi
    
    # Stop any existing containers
    docker-compose -f docker-compose.test.yml down -v
    
    # Build images
    docker-compose -f docker-compose.test.yml build --no-cache
    
    # Start services
    docker-compose -f docker-compose.test.yml up -d
    
    # Wait for services to be healthy
    services=("arbitrage-bot-geth-node-1" "arbitrage-bot-redis-1" "arbitrage-bot-prometheus-1")
    for service in "${services[@]}"; do
        check_health $service || exit 1
    done
    
    echo "Environment is ready!"
}

# Function to run tests
run_tests() {
    echo "Running tests..."
    docker-compose -f docker-compose.test.yml exec arbitrage-bot python -m pytest test/test_latency_optimization.py -v
    exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        echo "Tests failed. Printing logs..."
        docker-compose -f docker-compose.test.yml logs --tail=100 geth-node
        docker-compose -f docker-compose.test.yml logs --tail=100 arbitrage-bot
    fi
    
    return $exit_code
}

# Function to stop the environment
stop_env() {
    echo "Stopping Docker environment..."
    docker-compose -f docker-compose.test.yml down -v
}

# Main script
case "$1" in
    start)
        start_env
        ;;
    test)
        run_tests
        ;;
    stop)
        stop_env
        ;;
    *)
        echo "Usage: $0 {start|test|stop}"
        exit 1
        ;;
esac
