#!/bin/bash
set -e

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Clean up any existing containers
log "Cleaning up old containers..."
docker-compose -f docker-compose.minimal.yml down -v 2>/dev/null || true

# Build containers
log "Building containers..."
DOCKER_BUILDKIT=1 docker-compose -f docker-compose.minimal.yml build --no-cache

# Start services
log "Starting services..."
docker-compose -f docker-compose.minimal.yml up -d

# Wait for services to be healthy
log "Waiting for services to be ready..."
attempt=1
max_attempts=30
until docker-compose -f docker-compose.minimal.yml ps | grep -q "healthy" || [ $attempt -eq $max_attempts ]; do
    echo "Attempt $attempt/$max_attempts..."
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    log "Error: Services failed to become healthy"
    docker-compose -f docker-compose.minimal.yml logs
    docker-compose -f docker-compose.minimal.yml down -v
    exit 1
fi

# Run test
log "Running latency optimization test..."
docker-compose -f docker-compose.minimal.yml exec -T arbitrage-bot python -m pytest test/test_latency_optimization.py -v
EXIT_CODE=$?

# Print logs if test failed
if [ $EXIT_CODE -ne 0 ]; then
    log "Test failed. Printing logs..."
    docker-compose -f docker-compose.minimal.yml logs
fi

# Clean up
log "Cleaning up..."
docker-compose -f docker-compose.minimal.yml down -v

exit $EXIT_CODE
