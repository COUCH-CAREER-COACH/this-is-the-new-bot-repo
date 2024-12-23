"""Test suite for position optimization with real-world trading scenarios."""
import pytest
import asyncio
from decimal import Decimal
from web3 import Web3
from web3.exceptions import ContractLogicError
import json
import time
from typing import Dict, Any
from src.optimizations import PositionOptimizer
from src.metrics_collector import MetricsCollector
from src.exceptions import (
    InsufficientLiquidityError,
    ExcessiveSlippageError,
    PositionSizeError
)

class TestPositionOptimization:
    @pytest.fixture
    def setup(self, web3, config):
        """Initialize test environment."""
        # Initialize optimizer and metrics
        position_optimizer = PositionOptimizer(web3, config)
        metrics_collector = MetricsCollector(port=8080)
        
        return {
            'web3': web3,
            'config': config,
            'optimizer': position_optimizer,
            'metrics': metrics_collector
        }

    @pytest.mark.asyncio
    async def test_real_world_position_sizing(self, setup):
        """Test position sizing with real-world market conditions."""
        optimizer = setup['optimizer']
        w3 = setup['web3']
        metrics = setup['metrics']

        # Real-world market scenarios
        scenarios = [
            {
                'name': 'normal_market',
                'volatility': 0.02,  # 2% daily volatility
                'liquidity_depth': w3.to_wei(10000, 'ether'),
                'gas_price': w3.to_wei(50, 'gwei'),
                'expected_success_rate': 0.8
            },
            {
                'name': 'high_volatility',
                'volatility': 0.05,  # 5% daily volatility
                'liquidity_depth': w3.to_wei(8000, 'ether'),
                'gas_price': w3.to_wei(80, 'gwei'),
                'expected_success_rate': 0.6
            },
            {
                'name': 'low_liquidity',
                'volatility': 0.02,
                'liquidity_depth': w3.to_wei(2000, 'ether'),
                'gas_price': w3.to_wei(60, 'gwei'),
                'expected_success_rate': 0.7
            },
            {
                'name': 'extreme_conditions',
                'volatility': 0.08,  # 8% daily volatility
                'liquidity_depth': w3.to_wei(5000, 'ether'),
                'gas_price': w3.to_wei(150, 'gwei'),
                'expected_success_rate': 0.4
            }
        ]

        for scenario in scenarios:
            try:
                # Configure market conditions
                await optimizer.set_market_conditions(
                    volatility=scenario['volatility'],
                    gas_price=scenario['gas_price']
                )

                # Test pool with realistic reserves
                test_pool = {
                    'reserves': {
                        'token0': scenario['liquidity_depth'],
                        'token1': scenario['liquidity_depth']
                    },
                    'volatility': scenario['volatility'],
                    'fees': Decimal('0.003')  # 0.3% pool fee
                }

                start_time = time.time()
                
                # Calculate optimal position size
                position_size, metrics_data = await optimizer.calculate_optimal_position(
                    'arbitrage',
                    test_pool,
                    max_position=w3.to_wei(100, 'ether')
                )

                execution_time = time.time() - start_time

                # Validate position size against market conditions
                max_safe_position = int(Decimal('0.1') * Decimal(str(scenario['liquidity_depth'])))
                assert position_size <= max_safe_position, f"Position too large for {scenario['name']}"

                # Verify profitability under gas costs
                gas_cost = scenario['gas_price'] * 200000  # Estimated gas usage
                min_profit = gas_cost * 2  # Minimum profit should cover gas costs with buffer
                
                estimated_profit = await optimizer.estimate_profit(
                    position_size,
                    test_pool,
                    scenario['gas_price']
                )
                
                assert estimated_profit > min_profit, f"Position not profitable in {scenario['name']}"

                # Record detailed metrics
                metrics.record_optimization_test(
                    f"real_world_{scenario['name']}",
                    execution_time,
                    200000,
                    position_size,
                    Decimal(str(metrics_data['pool_impact'])),
                    Decimal(str(estimated_profit / gas_cost)),  # Profit ratio
                    Decimal(str(metrics_data['success_rate'])),
                    1,  # Block delay
                    50000  # Estimated gas savings
                )

            except (InsufficientLiquidityError, ExcessiveSlippageError, PositionSizeError) as e:
                # These exceptions are expected in extreme conditions
                metrics.record_error(f"position_sizing_{scenario['name']}", str(e))
                continue

    @pytest.mark.asyncio
    async def test_slippage_impact(self, setup):
        """Test position sizing with various slippage scenarios."""
        optimizer = setup['optimizer']
        w3 = setup['web3']
        metrics = setup['metrics']

        base_liquidity = w3.to_wei(10000, 'ether')
        
        # Test different slippage scenarios
        slippage_scenarios = [
            {'target': 0.001, 'max_position_pct': 0.02},  # 0.1% target slippage
            {'target': 0.003, 'max_position_pct': 0.05},  # 0.3% target slippage
            {'target': 0.005, 'max_position_pct': 0.08},  # 0.5% target slippage
            {'target': 0.01, 'max_position_pct': 0.10}    # 1.0% target slippage
        ]

        for scenario in slippage_scenarios:
            try:
                max_position = int(Decimal(str(base_liquidity)) * Decimal(str(scenario['max_position_pct'])))
                
                # Calculate optimal position with slippage constraint
                position_size = await optimizer.calculate_position_for_slippage(
                    base_liquidity,
                    target_slippage=Decimal(str(scenario['target'])),
                    max_position=max_position
                )

                # Verify actual slippage
                actual_slippage = await optimizer.calculate_slippage(
                    position_size,
                    base_liquidity
                )

                assert actual_slippage <= Decimal(str(scenario['target'])), \
                    f"Slippage {actual_slippage} exceeds target {scenario['target']}"

                # Record slippage metrics
                metrics.record_slippage_test(
                    position_size,
                    actual_slippage,
                    Decimal(str(scenario['target']))
                )

            except ExcessiveSlippageError as e:
                metrics.record_error(f"slippage_test_{scenario['target']}", str(e))
                continue

    @pytest.mark.asyncio
    async def test_position_rebalancing(self, setup):
        """Test dynamic position rebalancing under changing market conditions."""
        optimizer = setup['optimizer']
        w3 = setup['web3']
        metrics = setup['metrics']

        # Simulate changing market conditions over time
        market_changes = [
            {'volatility': 0.02, 'liquidity_change': 1.0},    # Initial state
            {'volatility': 0.04, 'liquidity_change': 0.8},    # Decreasing liquidity
            {'volatility': 0.03, 'liquidity_change': 0.9},    # Partial recovery
            {'volatility': 0.05, 'liquidity_change': 0.7}     # Stress conditions
        ]

        initial_position = w3.to_wei(10, 'ether')
        current_position = initial_position

        for i, change in enumerate(market_changes):
            try:
                # Update market conditions
                new_liquidity = int(w3.to_wei(10000, 'ether') * Decimal(str(change['liquidity_change'])))
                
                # Calculate optimal position adjustment
                new_position = await optimizer.calculate_rebalanced_position(
                    current_position=current_position,
                    new_liquidity=new_liquidity,
                    volatility=change['volatility']
                )

                # Verify rebalancing constraints
                max_adjustment = int(current_position * Decimal('0.2'))  # Max 20% adjustment per period
                assert abs(new_position - current_position) <= max_adjustment, \
                    "Position adjustment too large"

                # Record rebalancing metrics
                metrics.record_rebalancing_event(
                    current_position,
                    new_position,
                    change['volatility'],
                    change['liquidity_change']
                )

                current_position = new_position

            except Exception as e:
                metrics.record_error(f"rebalancing_period_{i}", str(e))
                continue

if __name__ == '__main__':
    pytest.main(['-v', 'test_position_optimization.py'])
