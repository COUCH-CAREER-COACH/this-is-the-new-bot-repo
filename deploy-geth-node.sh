#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1${NC}"
    else
        echo -e "${RED}✗ $1${NC}"
        exit 1
    fi
}

echo -e "${YELLOW}Starting Ethereum Node Deployment${NC}"

# Check for required tools
echo "Checking required tools..."
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker is required but not installed${NC}" >&2; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo -e "${RED}Docker Compose is required but not installed${NC}" >&2; exit 1; }

# Create required directories
echo "Creating directories..."
mkdir -p geth-data
mkdir -p grafana/dashboards
check_status "Created directories"

# Set correct permissions
echo "Setting permissions..."
chmod +x setup-geth.sh
check_status "Set permissions"

# Check disk space
echo "Checking disk space..."
FREE_SPACE=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "$FREE_SPACE" -lt 2000 ]; then
    echo -e "${RED}Warning: Less than 2TB free space available (${FREE_SPACE}GB)${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check memory
echo "Checking memory..."
TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
if [ "$TOTAL_MEM" -lt 32 ]; then
    echo -e "${RED}Warning: Less than 32GB RAM available (${TOTAL_MEM}GB)${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Configure firewall
echo "Configuring firewall..."
if command -v ufw >/dev/null 2>&1; then
    sudo ufw allow 30303/tcp  # P2P
    sudo ufw allow 30303/udp  # P2P
    sudo ufw allow 8545/tcp   # RPC
    sudo ufw allow 8546/tcp   # WebSocket
    check_status "Configured firewall"
else
    echo -e "${YELLOW}UFW not found. Please configure your firewall manually${NC}"
fi

# Set up system optimizations
echo "Setting up system optimizations..."
if [ -w /etc/sysctl.conf ]; then
    # Network optimizations
    echo "net.core.rmem_max=2500000" | sudo tee -a /etc/sysctl.conf
    echo "net.core.wmem_max=2500000" | sudo tee -a /etc/sysctl.conf
    echo "net.ipv4.tcp_rmem=4096 87380 2500000" | sudo tee -a /etc/sysctl.conf
    echo "net.ipv4.tcp_wmem=4096 87380 2500000" | sudo tee -a /etc/sysctl.conf
    
    # Apply changes
    sudo sysctl -p
    check_status "Applied system optimizations"
else
    echo -e "${YELLOW}Cannot write to sysctl.conf. Please optimize system manually${NC}"
fi

# Start services
echo "Starting services..."
docker-compose -f docker-compose.geth.yml up -d
check_status "Started services"

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 30

# Check if services are running
echo "Checking service status..."
docker-compose -f docker-compose.geth.yml ps | grep "Up" >/dev/null 2>&1
check_status "Services are running"

# Test node connection
echo "Testing node connection..."
curl -s -X POST -H "Content-Type: application/json" \
    --data '{"jsonrpc":"2.0","method":"net_version","params":[],"id":1}' \
    http://localhost:8545 >/dev/null 2>&1
check_status "Node is responding"

echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "
${YELLOW}Next steps:${NC}
1. Access Grafana: http://localhost:3000
2. Access Prometheus: http://localhost:9090
3. Check node sync status:
   curl -X POST -H \"Content-Type: application/json\" \\
        --data '{\"jsonrpc\":\"2.0\",\"method\":\"eth_syncing\",\"params\":[],\"id\":1}' \\
        http://localhost:8545

${YELLOW}Monitor your node:${NC}
- Check logs: docker-compose -f docker-compose.geth.yml logs -f geth
- View metrics in Grafana dashboard
- Monitor system resources

${YELLOW}Important:${NC}
- Initial sync may take several days
- Ensure sufficient disk space
- Monitor system resources
- Regularly check for updates
"

# Create a simple health check script
echo "Creating health check script..."
cat > check-node-health.sh << 'EOF'
#!/bin/bash

check_service() {
    docker-compose -f docker-compose.geth.yml ps | grep $1 | grep "Up" >/dev/null 2>&1
    return $?
}

check_node_response() {
    curl -s -X POST -H "Content-Type: application/json" \
        --data '{"jsonrpc":"2.0","method":"net_version","params":[],"id":1}' \
        http://localhost:8545 >/dev/null 2>&1
    return $?
}

echo "Checking node health..."
check_service "geth" && echo "✓ Geth is running" || echo "✗ Geth is not running"
check_service "prometheus" && echo "✓ Prometheus is running" || echo "✗ Prometheus is not running"
check_service "grafana" && echo "✓ Grafana is running" || echo "✗ Grafana is not running"
check_node_response && echo "✓ Node is responding" || echo "✗ Node is not responding"

# Check disk space
FREE_SPACE=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
echo "Available disk space: ${FREE_SPACE}GB"
if [ "$FREE_SPACE" -lt 100 ]; then
    echo "⚠️  Warning: Low disk space"
fi

# Check memory usage
FREE_MEM=$(free -g | awk '/^Mem:/{print $4}')
echo "Available memory: ${FREE_MEM}GB"
if [ "$FREE_MEM" -lt 4 ]; then
    echo "⚠️  Warning: Low memory"
fi
EOF

chmod +x check-node-health.sh
check_status "Created health check script"

echo -e "${GREEN}Setup complete! Run ./check-node-health.sh to monitor your node's health${NC}"
