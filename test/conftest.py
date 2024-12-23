"""Test configuration and fixtures."""
import pytest
import asyncio
import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, AsyncGenerator
from web3 import Web3
from eth_account import Account
import os

from src.exceptions import NetworkError

logger = logging.getLogger(__name__)

from src.optimizations import (
    GasOptimizer,
    LatencyOptimizer,
    PositionOptimizer,
    RiskManager
)
from src.arbitrage_strategy_v2 import EnhancedArbitrageStrategy
from src.jit_strategy import JustInTimeLiquidityStrategy
from src.sandwich_strategy_new import EnhancedSandwichStrategy
from src.metrics_collector import MetricsCollector
from src.utils.dex_utils import DEXHandler
from src.flashbots import FlashbotsManager
from src.mock_flash_loan import MockFlashLoan

# Constants for testing
TEST_PRIVATE_KEY = "0x" + "1" * 64
TEST_ACCOUNT = Account.from_key(TEST_PRIVATE_KEY)
ZERO_ADDRESS = "0x" + "0" * 40

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def web3():
    """Initialize Web3 with local Ganache provider for testing."""
    w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
    w3.eth.default_account = TEST_ACCOUNT.address
    # Ensure connection
    assert w3.is_connected(), "Web3 is not connected to local node"
    return w3

@pytest.fixture(scope="session")
def config():
    """Load test configuration."""
    config_path = Path(__file__).parent.parent / "config" / "test.local.config.json"
    with open(config_path, "r") as f:
        return json.load(f)

@pytest.fixture(scope="session")
def flash_loan(web3, config):
    """Initialize mock flash loan manager."""
    return MockFlashLoan(web3, config)

@pytest.fixture(scope="session")
def arbitrage_strategy(web3, config, flash_loan):
    """Initialize enhanced arbitrage strategy with mock flash loan."""
    strategy = EnhancedArbitrageStrategy(web3, config)
    strategy.flash_loan = flash_loan  # Override with mock flash loan
    return strategy

@pytest.fixture(scope="session")
def jit_strategy(web3, config):
    """Initialize JIT liquidity strategy."""
    return JustInTimeLiquidityStrategy(web3, config)

@pytest.fixture(scope="session")
def sandwich_strategy(web3, config):
    """Initialize enhanced sandwich strategy."""
    return EnhancedSandwichStrategy(web3, config)

@pytest.fixture(scope="class")
async def metrics() -> AsyncGenerator[MetricsCollector, None]:
    """Initialize metrics collector with local tmp directory."""
    metrics_dir = os.path.join(os.getcwd(), 'tmp')
    os.makedirs(metrics_dir, exist_ok=True)
    
    # Create collector with random port
    collector = MetricsCollector(metrics_dir=metrics_dir)
    
    yield collector
    
    # Cleanup
    try:
        collector.cleanup()
    except Exception as e:
        print(f"Warning: Failed to cleanup metrics: {e}")

@pytest.fixture(scope="session")
def gas_optimizer(web3, config):
    """Initialize gas optimizer."""
    return GasOptimizer(web3, config)

@pytest.fixture(scope="class")
async def latency_optimizer(web3, config) -> AsyncGenerator[LatencyOptimizer, None]:
    """Initialize latency optimizer with optional WebSocket support."""
    try:
        # Try to create WebSocket provider
        ws_provider = Web3.WebsocketProvider('ws://localhost:8546', websocket_timeout=60)
        ws_w3 = Web3(ws_provider)
        if not ws_w3.is_connected():
            logger.warning("WebSocket connection failed, continuing with HTTP only")
            ws_w3 = None
    except Exception as e:
        logger.warning(f"WebSocket initialization failed: {e}. Continuing with HTTP only.")
        ws_w3 = None
    
    # Initialize optimizer with default config if none provided
    if not config:
        config = {
            'optimization': {
                'latency': {
                    'max_acceptable': 0.1,
                    'warning_threshold': 0.08,
                    'critical_threshold': 0.15,
                    'max_retries': 3,
                    'retry_delay': 0.05,
                    'ws_ping_interval': 5,
                    'ws_timeout': 3,
                    'parallel_requests': 4
                },
                'mempool': {
                    'max_pending_tx': 5000,
                    'cleanup_interval': 100
                }
            },
            'network': {
                'block_time': 12
            }
        }
    
    # Initialize optimizer
    optimizer = LatencyOptimizer(web3, ws_w3, config)
    optimizer.monitoring_active = False
    optimizer.max_pending = config['optimization']['mempool']['max_pending_tx']
    optimizer.target_block_time = config['network']['block_time']
    
    logger.info("LatencyOptimizer initialized successfully")
    
    yield optimizer
    
    # Cleanup
    if ws_w3 and hasattr(ws_w3.provider, 'disconnect'):
        try:
            await ws_w3.provider.disconnect()
        except Exception as e:
            logger.warning(f"Error during WebSocket cleanup: {e}")

@pytest.fixture(scope="session")
def position_optimizer(web3, config):
    """Initialize position optimizer."""
    return PositionOptimizer(web3, config)

@pytest.fixture(scope="session")
def risk_manager(web3, config):
    """Initialize risk manager."""
    return RiskManager(web3, config)

@pytest.fixture(scope="session")
def dex_handler(web3, config):
    """Initialize DEX handler."""
    return DEXHandler(web3, config)

@pytest.fixture(scope="session")
def flashbots_manager(web3, config):
    """Initialize Flashbots manager."""
    return FlashbotsManager(
        web3,
        TEST_PRIVATE_KEY,
        "https://relay.flashbots.net"
    )

@pytest.fixture(autouse=True)
async def run_around_tests():
    """Setup and teardown for each test."""
    # Setup
    metrics_dir = os.path.join(os.getcwd(), 'tmp')
    os.makedirs(metrics_dir, exist_ok=True)
    
    yield
    
    # Teardown
    try:
        # Kill any hanging processes
        os.system('pkill -f "node|ganache|geth"')
        
        # Clean up temporary files
        for root, dirs, files in os.walk(metrics_dir):
            for file in files:
                try:
                    os.remove(os.path.join(root, file))
                except Exception:
                    pass
    except Exception as e:
        print(f"Warning: Failed to cleanup after tests: {e}")
