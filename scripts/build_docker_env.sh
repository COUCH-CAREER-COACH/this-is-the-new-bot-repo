#!/bin/bash
set -e

# Function to create combined requirements file
create_requirements() {
    echo "Creating combined requirements file..."
    cat > docker-requirements.txt << EOL
# Core Dependencies from requirements.txt
web3==6.11.3
python-dotenv==1.0.0
eth-account==0.9.0
requests==2.31.0
python-json-logger==2.0.7

# Testing Dependencies
pytest==7.4.0
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-xdist==3.3.1
pytest-timeout==2.1.0

# Ethereum Dependencies
eth-typing==3.4.0
eth-utils==2.2.0

# Data Analysis and Visualization
pandas==2.0.3
matplotlib==3.7.2
seaborn==0.12.2

# Monitoring and Metrics
prometheus-client==0.17.1

# Async Support
aiohttp==3.8.5
asyncio==3.4.3

# Type Checking
mypy==1.4.1
types-requests==2.31.0.2
types-setuptools==68.0.0.3

# Code Quality
black==23.7.0
flake8==6.1.0
isort==5.12.0

# Documentation
sphinx==6.2.1
sphinx-rtd-theme==1.2.2

# Development Tools
ipython==8.14.0
jupyter==1.0.0
EOL
}

# Function to create Dockerfile
create_dockerfile() {
    echo "Creating Dockerfile..."
    cat > Dockerfile << EOL
# Use Python 3.11 as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    git \\
    netcat-traditional \\
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x (LTS) and npm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \\
    && apt-get update \\
    && DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs \\
    && npm install -g npm@latest \\
    && rm -rf /var/lib/apt/lists/*

# Copy entrypoint script first
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Copy requirements file
COPY docker-requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r docker-requirements.txt

# Copy project files
COPY . .

# Install npm packages
RUN npm install

# Create necessary directories
RUN mkdir -p \\
    logs \\
    reports \\
    optimization \\
    cache \\
    metrics \\
    tmp \\
    data/ganache \\
    && chmod -R 777 logs reports metrics tmp

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PROMETHEUS_MULTIPROC_DIR=/app/tmp

# Set permissions
RUN chmod +x scripts/*.sh

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Use the entrypoint script
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command (can be overridden)
CMD ["python", "-m", "pytest", "test/", "-v"]
EOL
}

# Main script
echo "Starting Docker environment setup..."

# Create necessary files
create_requirements
create_dockerfile

# Build and start containers
echo "Building Docker containers..."
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml build --no-cache
docker-compose -f docker-compose.test.yml up -d

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 30

# Run the test
echo "Running test..."
docker-compose -f docker-compose.test.yml exec arbitrage-bot python -m pytest test/test_latency_optimization.py -v

# Capture exit code
EXIT_CODE=$?

# Print logs if test failed
if [ $EXIT_CODE -ne 0 ]; then
    echo "Test failed. Printing container logs..."
    docker-compose -f docker-compose.test.yml logs --tail=100 geth-node
    docker-compose -f docker-compose.test.yml logs --tail=100 arbitrage-bot
fi

# Clean up
echo "Cleaning up..."
docker-compose -f docker-compose.test.yml down -v

exit $EXIT_CODE
