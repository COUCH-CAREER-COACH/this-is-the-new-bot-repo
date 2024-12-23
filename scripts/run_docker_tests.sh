#!/bin/bash
set -e

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check Docker daemon
check_docker() {
    log "Checking Docker daemon..."
    if ! docker info >/dev/null 2>&1; then
        log "Error: Docker daemon is not running"
        exit 1
    fi
}

# Function to clean up
cleanup() {
    log "Cleaning up containers and volumes..."
    docker-compose -f docker-compose.test.yml down -v
}

# Function to wait for service health
wait_for_service() {
    local service=$1
    local max_attempts=30
    local attempt=1

    log "Waiting for $service to be healthy..."
    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f docker-compose.test.yml ps $service | grep -q "healthy"; then
            log "$service is healthy"
            return 0
        fi
        log "Attempt $attempt/$max_attempts: $service not healthy yet"
        sleep 2
        attempt=$((attempt + 1))
    done

    log "Error: $service failed to become healthy"
    return 1
}

# Set up error handling
trap cleanup EXIT

# Start setup
log "Starting test environment setup..."

# Check Docker
check_docker

# Clean up any existing containers
cleanup

# Create necessary directories
log "Creating directories..."
mkdir -p logs reports metrics tmp
chmod -R 777 logs reports metrics tmp

# Build containers
log "Building containers..."
docker-compose -f docker-compose.test.yml build --no-cache

# Start services
log "Starting services..."
docker-compose -f docker-compose.test.yml up -d

# Wait for services
wait_for_service geth || exit 1
wait_for_service redis || exit 1
wait_for_service prometheus || exit 1

# Run tests
log "Running tests..."
docker-compose -f docker-compose.test.yml exec -T test pytest test/test_latency_optimization.py -v
TEST_EXIT_CODE=$?

# Check test results
if [ $TEST_EXIT_CODE -ne 0 ]; then
    log "Tests failed. Printing logs..."
    docker-compose -f docker-compose.test.yml logs
    exit $TEST_EXIT_CODE
fi

log "Tests completed successfully"
exit 0
