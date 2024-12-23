#!/bin/bash
set -e

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting latency test setup..."

# Create minimal requirements
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Creating requirements..."
cat > docker-requirements.txt << EOL
web3==6.11.3
pytest==7.4.0
pytest-asyncio==0.21.1
pytest-timeout==2.1.0
eth-account==0.9.0
eth-typing==3.4.0
eth-utils==2.2.0
aiohttp==3.8.5
EOL

# Create minimal Dockerfile
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Creating Dockerfile..."
cat > Dockerfile << EOL
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl netcat-traditional && rm -rf /var/lib/apt/lists/*
COPY docker-requirements.txt .
RUN pip install --no-cache-dir -r docker-requirements.txt
COPY . .
CMD ["python", "-m", "pytest", "test/test_latency_optimization.py", "-v"]
EOL

# Clean up any existing containers
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaning up..."
docker-compose -f docker-compose.test.yml down -v 2>/dev/null || true

# Build and run
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Building containers..."
docker-compose -f docker-compose.test.yml build --no-cache

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting containers..."
docker-compose -f docker-compose.test.yml up -d

# Wait for services
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for services..."
sleep 15

# Run test
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running test..."
docker-compose -f docker-compose.test.yml exec -T arbitrage-bot python -m pytest test/test_latency_optimization.py -v
EXIT_CODE=$?

# Print logs if failed
if [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Test failed. Printing logs..."
    docker-compose -f docker-compose.test.yml logs
fi

# Cleanup
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaning up..."
docker-compose -f docker-compose.test.yml down -v

exit $EXIT_CODE
