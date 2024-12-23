"""Test suite for gas optimization."""
import pytest
import asyncio
from decimal import Decimal
from web3 import Web3
import json
import time
from src.optimizations import GasOptimizer
from src.metrics_collector import MetricsCollector

class TestGasOptimization:
    @pytest.fixture
    def setup(self, web3, config):
        """Initialize test environment."""
        # Initialize optimizer and metrics
        gas_optimizer = GasOptimizer(web3, config)
        metrics_collector = MetricsCollector(port=8080)
        
        return {
            'web3': web3,
            'config': config,
            'optimizer': gas_optimizer,
            'metrics': metrics_collector
        }

    @pytest.mark.asyncio
    async def test_gas_price_estimation(self, setup):
        """Test gas price estimation for different strategies."""
        optimizer = setup['optimizer']
        metrics = setup['metrics']
        w3 = setup['web3']

        strategies = ['arbitrage', 'jit', 'sandwich_frontrun']
        for strategy in strategies:
            start_time = time.time()
            
            gas_price = await optimizer.estimate_optimal_gas_price(strategy)
            assert gas_price > 0, f"Gas price should be positive for {strategy}"
            assert gas_price <= optimizer.max_gas_price, f"Gas price should not exceed max for {strategy}"
            
            # Record metrics
            execution_time = time.time() - start_time
            metrics.record_execution_time(strategy, execution_time)
            metrics.update_gas_price(gas_price)

    @pytest.mark.asyncio
    async def test_transaction_batching(self, setup):
        """Test transaction batching functionality."""
        optimizer = setup['optimizer']
        w3 = setup['web3']
        metrics = setup['metrics']

        test_txs = [
            {
                'to': setup['config']['dex']['uniswap_v2_router'],
                'function': 'swapExactTokensForTokens',
                'args': [
                    w3.to_wei(1, 'ether'),
                    0,
                    [
                        setup['config']['test_tokens']['WETH'],
                        setup['config']['test_tokens']['USDC']
                    ],
                    w3.eth.default_account,
                    w3.eth.get_block('latest')['timestamp'] + 1200
                ],
                'gas': 200000
            },
            {
                'to': setup['config']['dex']['sushiswap_router'],
                'function': 'swapExactTokensForTokens',
                'args': [
                    w3.to_wei(1, 'ether'),
                    0,
                    [
                        setup['config']['test_tokens']['WETH'],
                        setup['config']['test_tokens']['DAI']
                    ],
                    w3.eth.default_account,
                    w3.eth.get_block('latest')['timestamp'] + 1200
                ],
                'gas': 200000
            }
        ]
        
        start_time = time.time()
        tx_hash = await optimizer.batch_transactions(test_txs)
        execution_time = time.time() - start_time
        
        assert tx_hash is not None, "Transaction batching should return tx hash"
        
        # Record batching metrics
        metrics.record_execution_time('batch_transactions', execution_time)
        metrics.record_gas_usage('batch_transactions', 400000, 100000)  # Estimated gas savings

    @pytest.mark.asyncio
    async def test_gas_optimization_under_load(self, setup):
        """Test gas optimization under heavy network load."""
        optimizer = setup['optimizer']
        metrics = setup['metrics']
        w3 = setup['web3']
        
        # Simulate heavy network load
        await optimizer.simulate_network_conditions(
            base_fee=w3.to_wei(150, 'gwei'),
            priority_fee=w3.to_wei(10, 'gwei'),
            block_usage=0.98
        )
        
        try:
            # Test rapid gas price updates
            for _ in range(10):
                gas_price = await optimizer.estimate_optimal_gas_price('arbitrage')
                await asyncio.sleep(0.1)  # Simulate rapid updates
                
                # Verify gas price adaptation
                new_gas_price = await optimizer.estimate_optimal_gas_price('arbitrage')
                assert abs(new_gas_price - gas_price) <= w3.to_wei(5, 'gwei'), \
                    "Gas price should not fluctuate too rapidly"
                
                metrics.update_gas_price(new_gas_price)
                
        except Exception as e:
            metrics.record_error('gas_optimization_load_test', str(e))
            raise

if __name__ == '__main__':
    pytest.main(['-v', 'test_gas_optimization.py'])
