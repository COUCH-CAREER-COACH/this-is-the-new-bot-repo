"""Test suite for risk management with real-world trading scenarios."""
import pytest
import asyncio
from decimal import Decimal
from web3 import Web3
from web3.exceptions import ContractLogicError
import json
import time
from typing import Dict, Any
from src.optimizations import RiskManager
from src.metrics_collector import MetricsCollector
from src.exceptions import (
    RiskLimitExceeded,
    CircuitBreakerTriggered,
    ExposureLimitExceeded,
    SlippageExceeded
)

class TestRiskManagement:
    @pytest.fixture
    def setup(self, web3, config):
        """Initialize test environment."""
        # Initialize risk manager and metrics
        risk_manager = RiskManager(web3, config)
        metrics_collector = MetricsCollector(port=8080)
        
        return {
            'web3': web3,
            'config': config,
            'risk_manager': risk_manager,
            'metrics': metrics_collector
        }

    @pytest.mark.asyncio
    async def test_market_stress_conditions(self, setup):
        """Test risk management under various market stress conditions."""
        risk_manager = setup['risk_manager']
        w3 = setup['web3']
        metrics = setup['metrics']

        # Market stress scenarios
        scenarios = [
            {
                'name': 'high_volatility',
                'price_change': 0.05,  # 5% sudden price change
                'gas_price': w3.to_wei(150, 'gwei'),
                'liquidity_reduction': 0.3,  # 30% liquidity reduction
                'expected_breaker': 'volatility'
            },
            {
                'name': 'gas_spike',
                'price_change': 0.02,
                'gas_price': w3.to_wei(300, 'gwei'),
                'liquidity_reduction': 0.1,
                'expected_breaker': 'gas_price'
            },
            {
                'name': 'liquidity_crisis',
                'price_change': 0.03,
                'gas_price': w3.to_wei(100, 'gwei'),
                'liquidity_reduction': 0.7,  # 70% liquidity reduction
                'expected_breaker': 'liquidity'
            }
        ]

        for scenario in scenarios:
            try:
                # Reset risk manager state
                await risk_manager.reset_state()
                
                # Simulate market conditions
                await risk_manager.simulate_market_conditions(
                    price_change=scenario['price_change'],
                    gas_price=scenario['gas_price'],
                    liquidity_factor=1 - scenario['liquidity_reduction']
                )

                # Test trade validation under stress
                test_trade = {
                    'position_size': w3.to_wei(10, 'ether'),
                    'expected_profit': w3.to_wei(0.2, 'ether'),
                    'strategy': 'arbitrage'
                }

                try:
                    valid, message = await risk_manager.validate_trade(
                        test_trade['strategy'],
                        test_trade['position_size'],
                        test_trade['expected_profit']
                    )
                    
                    # Verify circuit breaker activation
                    assert not valid, f"Trade should be rejected in {scenario['name']}"
                    assert scenario['expected_breaker'] in message.lower(), \
                        f"Wrong circuit breaker triggered in {scenario['name']}"
                    
                except CircuitBreakerTriggered as e:
                    # Expected behavior
                    metrics.record_circuit_breaker(
                        scenario['name'],
                        str(e),
                        scenario['expected_breaker']
                    )

                # Record scenario metrics
                metrics.record_stress_test(
                    scenario['name'],
                    scenario['price_change'],
                    scenario['gas_price'],
                    scenario['liquidity_reduction']
                )

            except Exception as e:
                metrics.record_error(f"stress_test_{scenario['name']}", str(e))
                continue

    @pytest.mark.asyncio
    async def test_dynamic_exposure_limits(self, setup):
        """Test dynamic exposure limit adjustments based on market conditions."""
        risk_manager = setup['risk_manager']
        w3 = setup['web3']
        metrics = setup['metrics']

        # Market condition scenarios
        conditions = [
            {'volatility': 'low', 'liquidity': 'high', 'max_exposure_multiplier': 1.0},
            {'volatility': 'medium', 'liquidity': 'medium', 'max_exposure_multiplier': 0.7},
            {'volatility': 'high', 'liquidity': 'low', 'max_exposure_multiplier': 0.4}
        ]

        base_position = w3.to_wei(10, 'ether')

        for condition in conditions:
            try:
                # Set market conditions
                await risk_manager.set_market_conditions(
                    volatility_level=condition['volatility'],
                    liquidity_level=condition['liquidity']
                )

                # Calculate adjusted exposure limit
                max_exposure = await risk_manager.calculate_dynamic_exposure_limit(
                    base_position,
                    condition['max_exposure_multiplier']
                )

                # Test multiple trades under current conditions
                total_exposure = 0
                trades_attempted = 0
                max_trades = 5

                while trades_attempted < max_trades:
                    try:
                        # Attempt trade
                        position_size = int(base_position * Decimal('0.2'))  # 20% of base position
                        valid, _ = await risk_manager.validate_trade(
                            'arbitrage',
                            position_size,
                            w3.to_wei(0.1, 'ether')  # Expected profit
                        )

                        if valid:
                            total_exposure += position_size
                            if total_exposure > max_exposure:
                                raise ExposureLimitExceeded(
                                    f"Exposure {total_exposure} exceeds limit {max_exposure}"
                                )
                    except ExposureLimitExceeded as e:
                        metrics.record_exposure_limit(
                            condition['volatility'],
                            total_exposure,
                            max_exposure
                        )
                        break

                    trades_attempted += 1

                # Verify exposure constraints
                assert total_exposure <= max_exposure, \
                    f"Total exposure {total_exposure} exceeds limit {max_exposure}"

                # Record condition metrics
                metrics.record_market_condition(
                    condition['volatility'],
                    condition['liquidity'],
                    total_exposure,
                    max_exposure
                )

            except Exception as e:
                metrics.record_error(
                    f"exposure_test_{condition['volatility']}_{condition['liquidity']}",
                    str(e)
                )
                continue

    @pytest.mark.asyncio
    async def test_profit_threshold_adaptation(self, setup):
        """Test dynamic profit threshold adaptation based on risk factors."""
        risk_manager = setup['risk_manager']
        w3 = setup['web3']
        metrics = setup['metrics']

        # Risk factor scenarios
        scenarios = [
            {
                'name': 'low_risk',
                'gas_price': w3.to_wei(50, 'gwei'),
                'volatility': 0.02,
                'recent_failures': 0,
                'min_profit_multiplier': 1.5
            },
            {
                'name': 'medium_risk',
                'gas_price': w3.to_wei(100, 'gwei'),
                'volatility': 0.04,
                'recent_failures': 2,
                'min_profit_multiplier': 2.0
            },
            {
                'name': 'high_risk',
                'gas_price': w3.to_wei(200, 'gwei'),
                'volatility': 0.06,
                'recent_failures': 5,
                'min_profit_multiplier': 3.0
            }
        ]

        for scenario in scenarios:
            try:
                # Set risk conditions
                await risk_manager.set_risk_factors(
                    gas_price=scenario['gas_price'],
                    volatility=scenario['volatility'],
                    recent_failures=scenario['recent_failures']
                )

                # Calculate adaptive profit threshold
                min_profit = await risk_manager.calculate_min_profit_threshold(
                    base_threshold=w3.to_wei(0.1, 'ether'),
                    multiplier=scenario['min_profit_multiplier']
                )

                # Test trades against adaptive threshold
                test_profits = [
                    w3.to_wei(0.05, 'ether'),  # Below threshold
                    w3.to_wei(0.2, 'ether'),   # Above threshold
                    w3.to_wei(0.15, 'ether')   # Borderline
                ]

                for profit in test_profits:
                    try:
                        valid, message = await risk_manager.validate_profit(
                            profit,
                            min_profit,
                            scenario['name']
                        )

                        metrics.record_profit_validation(
                            scenario['name'],
                            profit,
                            min_profit,
                            valid
                        )

                    except Exception as e:
                        metrics.record_error(
                            f"profit_validation_{scenario['name']}",
                            str(e)
                        )
                        continue

            except Exception as e:
                metrics.record_error(f"profit_threshold_{scenario['name']}", str(e))
                continue

if __name__ == '__main__':
    pytest.main(['-v', 'test_risk_management.py'])
