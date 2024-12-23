"""Test suite for strategy optimizations."""
import pytest
import asyncio
from decimal import Decimal
from web3 import Web3
import json
import time
from src.optimizations import GasOptimizer, LatencyOptimizer, PositionOptimizer, RiskManager
from src.metrics_collector import MetricsCollector

class TestOptimizations:
    @pytest.fixture(scope="class")
    async def setup(self):
        """Initialize test environment and load configuration."""
        # Load test configuration
        with open('config/test.config.json', 'r') as f:
            config = json.load(f)

        # Initialize Web3
        w3 = Web3(Web3.HTTPProvider(config['network']['http_provider']))
        
        # Initialize optimizers
        gas_optimizer = GasOptimizer(w3, config)
        latency_optimizer = LatencyOptimizer(w3, config)
        position_optimizer = PositionOptimizer(w3, config)
        risk_manager = RiskManager(w3, config)
        
        # Initialize metrics collector
        metrics_collector = MetricsCollector(port=8080)

        return {
            'web3': w3,
            'config': config,
            'optimizers': {
                'gas': gas_optimizer,
                'latency': latency_optimizer,
                'position': position_optimizer,
                'risk': risk_manager
            },
            'metrics': metrics_collector
        }
