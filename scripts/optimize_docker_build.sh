#!/bin/bash
set -e

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to create optimized requirements file
create_requirements() {
    log "Creating optimized requirements file..."
    cat > docker-requirements.txt << EOL
# Core Dependencies
web3==6.11.3
python-dotenv==1.0.0
eth-account==0.9.0
requests==2.31.0
python-json-logger==2.0.7

# Testing Dependencies (minimal set for latency tests)
pytest==7.4.0
pytest-asyncio==0.21.1
pytest-timeout==2.1.0

# Ethereum Dependencies
eth-typing==3.4.0
eth-utils==2.2.0

# Monitoring and Metrics
prometheus-client==0.17.1

# Async Support
aiohttp==3.8.5
EOL
}

# Function to create optimized Dockerfile
create_dockerfile() {
    log "Creating optimized Dockerfile..."
    cat > Dockerfile << EOL
FROM python:3.11-slim

WORKDIR /app

# Install only essential system dependencies
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
    curl \\
    netcat-traditional && \\
    rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x LTS
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \\
    apt-get update && \\
    apt-get install -y --no-install-recommends nodejs && \\
    npm install -g npm@latest && \\
    rm -rf /var/lib/apt/lists/*

# Copy and set up entrypoint
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Install Python dependencies
COPY docker-requirements.txt .
RUN pip install --no-cache-dir -r docker-requirements.txt

# Create necessary directories
RUN mkdir -p logs reports metrics tmp data/ganache && \\
    chmod -R 777 logs reports metrics tmp

# Set environment variables
ENV PYTHONPATH=/app \\
    PYTHONUNBUFFERED=1 \\
    PROMETHEUS_MULTIPROC_DIR=/app/tmp

# Copy only necessary project files
COPY src/ src/
COPY test/ test/
COPY config/ config/
COPY package*.json ./

# Install npm packages
RUN npm ci --only=production

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "-m", "pytest", "test/test_latency_optimization.py", "-v"]
EOL
}

# Function to check if Docker daemon is running
check_docker() {
    log "Checking Docker daemon..."
    if ! docker info >/dev/null 2>&1; then
        log "Error: Docker daemon is not running"
        exit 1
    fi
}

# Function to clean up old containers and images
cleanup() {
    log "Cleaning up old containers and images..."
    docker-compose -f docker-compose.test.yml down -v || true
    docker system prune -f
}

# Function to build with timeout
build_with_timeout() {
    log "Building Docker containers with 10-minute timeout..."
    timeout 600 docker-compose -f docker-compose.test.yml build --no-cache || {
        log "Error: Build timed out after 10 minutes"
        exit 1
    }
}

# Main script
log "Starting optimized Docker environment setup..."

# Check prerequisites
check_docker

# Clean up
cleanup

# Create optimized files
create_requirements
create_dockerfile

# Build and start containers
log "Building containers..."
build_with_timeout

log "Starting containers..."
docker-compose -f docker-compose.test.yml up -d

# Wait for services with timeout
log "Waiting for services (30s timeout)..."
timeout 30 bash -c 'until docker-compose -f docker-compose.test.yml ps | grep -q "healthy"; do sleep 1; done' || {
    log "Error: Services failed to become healthy within timeout"
    docker-compose -f docker-compose.test.yml logs
    exit 1
}

# Run the test
log "Running test..."
docker-compose -f docker-compose.test.yml exec -T arbitrage-bot python -m pytest test/test_latency_optimization.py -v
EXIT_CODE=$?

# Print logs if test failed
if [ $EXIT_CODE -ne 0 ]; then
    log "Test failed. Printing container logs..."
    docker-compose -f docker-compose.test.yml logs --tail=100
fi

# Clean up
log "Cleaning up..."
docker-compose -f docker-compose.test.yml down -v

exit $EXIT_CODE
