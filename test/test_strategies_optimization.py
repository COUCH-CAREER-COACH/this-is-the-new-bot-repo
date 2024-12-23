"""Test optimization strategies."""
import pytest
import asyncio
import json
from decimal import Decimal
from web3 import Web3

from src.arbitrage_strategy_v2 import EnhancedArbitrageStrategy
from src.jit_strategy import JustInTimeLiquidityStrategy
from src.sandwich_strategy_new import EnhancedSandwichStrategy
from src.logger_config import logger

class TestStrategiesOptimization:
    @pytest.mark.asyncio
    async def test_arbitrage_optimization(self, web3, config, arbitrage_strategy):
        """Test and optimize arbitrage strategy."""
        # Test parameters to optimize
        test_amounts = [
            web3.to_wei(1, 'ether'),
            web3.to_wei(5, 'ether'),
            web3.to_wei(10, 'ether'),
            web3.to_wei(20, 'ether')
        ]

        results = []
        for amount in test_amounts:
            # Create test swap transaction
            test_tx = {
                'hash': '0x' + '00' * 32,
                'to': config['dex']['uniswap_v2_router'],
                'value': amount,
                'gasPrice': web3.to_wei(50, 'gwei'),
                'input': '0x38ed1739'  # swapExactTokensForTokens
            }

            # Analyze opportunity
            opportunity = await arbitrage_strategy.analyze_transaction(test_tx)
            
            if opportunity:
                results.append({
                    'test_amount': amount,
                    'profit': opportunity['expected_profit'],
                    'gas_cost': opportunity['gas_price'] * 500000  # Approximate gas used
                })

        # Calculate optimal ranges
        if results:
            profitable_amounts = [r for r in results if r['profit'] > r['gas_cost']]
            if profitable_amounts:
                avg_profit = sum(r['profit'] for r in profitable_amounts) / len(profitable_amounts)
                logger.info(f"Arbitrage Strategy Optimization Results:")
                logger.info(f"Optimal trade size range: {min(profitable_amounts)['test_amount']} - {max(profitable_amounts)['test_amount']} wei")
                logger.info(f"Average expected profit: {avg_profit} wei")

    @pytest.mark.asyncio
    async def test_jit_optimization(self, web3, config, jit_strategy):
        """Test and optimize JIT liquidity strategy."""
        # Test parameters
        test_scenarios = [
            {
                'swap_amount': web3.to_wei(50, 'ether'),
                'pool_reserves': (web3.to_wei(1000, 'ether'), web3.to_wei(1000, 'ether')),
                'gas_price': web3.to_wei(50, 'gwei')
            },
            {
                'swap_amount': web3.to_wei(100, 'ether'),
                'pool_reserves': (web3.to_wei(2000, 'ether'), web3.to_wei(2000, 'ether')),
                'gas_price': web3.to_wei(100, 'gwei')
            }
        ]

        results = []
        for scenario in test_scenarios:
            # Create test transaction
            test_tx = {
                'hash': '0x' + '00' * 32,
                'to': config['dex']['uniswap_v2_router'],
                'value': scenario['swap_amount'],
                'gasPrice': scenario['gas_price'],
                'input': '0x38ed1739'
            }

            # Analyze opportunity
            opportunity = await jit_strategy.analyze_transaction(test_tx)
            
            if opportunity:
                results.append({
                    'scenario': scenario,
                    'liquidity_amount': opportunity['liquidity_amount'],
                    'expected_profit': opportunity['expected_profit']
                })

        # Analyze results
        if results:
            logger.info("JIT Strategy Optimization Results:")
            for result in results:
                profit_ratio = Decimal(str(result['expected_profit'])) / Decimal(str(result['scenario']['swap_amount']))
                logger.info(f"Swap Amount: {result['scenario']['swap_amount']} wei")
                logger.info(f"Optimal Liquidity: {result['liquidity_amount']} wei")
                logger.info(f"Profit Ratio: {profit_ratio}")

    @pytest.mark.asyncio
    async def test_sandwich_optimization(self, web3, config, sandwich_strategy):
        """Test and optimize sandwich strategy."""
        # Test different victim transaction sizes and gas prices
        test_scenarios = [
            {
                'victim_amount': web3.to_wei(10, 'ether'),
                'gas_price': web3.to_wei(30, 'gwei')
            },
            {
                'victim_amount': web3.to_wei(20, 'ether'),
                'gas_price': web3.to_wei(50, 'gwei')
            },
            {
                'victim_amount': web3.to_wei(30, 'ether'),
                'gas_price': web3.to_wei(70, 'gwei')
            }
        ]

        results = []
        for scenario in test_scenarios:
            # Create test victim transaction
            test_tx = {
                'hash': '0x' + '00' * 32,
                'to': config['dex']['uniswap_v2_router'],
                'value': scenario['victim_amount'],
                'gasPrice': scenario['gas_price'],
                'input': '0x38ed1739'
            }

            # Analyze opportunity
            opportunity = await sandwich_strategy.analyze_transaction(test_tx)
            
            if opportunity:
                results.append({
                    'scenario': scenario,
                    'frontrun_amount': opportunity['frontrun_amount'],
                    'backrun_amount': opportunity['backrun_amount'],
                    'expected_profit': opportunity['expected_profit'],
                    'competition_level': opportunity['competition_level']
                })

        # Analyze results
        if results:
            logger.info("Sandwich Strategy Optimization Results:")
            for result in results:
                profit_ratio = Decimal(str(result['expected_profit'])) / Decimal(str(result['scenario']['victim_amount']))
                logger.info(f"Victim Amount: {result['scenario']['victim_amount']} wei")
                logger.info(f"Optimal Frontrun: {result['frontrun_amount']} wei")
                logger.info(f"Optimal Backrun: {result['backrun_amount']} wei")
                logger.info(f"Profit Ratio: {profit_ratio}")
                logger.info(f"Competition Level: {result['competition_level']}")

    @pytest.mark.asyncio
    async def test_latency_optimization(self, web3, config, arbitrage_strategy, jit_strategy, sandwich_strategy):
        """Test and measure latency for all strategies."""
        strategies = {
            'arbitrage': arbitrage_strategy,
            'jit': jit_strategy,
            'sandwich': sandwich_strategy
        }

        # Create a standard test transaction
        test_tx = {
            'hash': '0x' + '00' * 32,
            'to': config['dex']['uniswap_v2_router'],
            'value': web3.to_wei(10, 'ether'),
            'gasPrice': web3.to_wei(50, 'gwei'),
            'input': '0x38ed1739'
        }

        latency_results = {}
        
        for name, strategy in strategies.items():
            start_time = web3.eth.get_block('latest')['timestamp']
            
            # Run analysis multiple times to get average
            iterations = 10
            total_time = 0
            
            for _ in range(iterations):
                before = web3.eth.get_block('latest')['timestamp']
                await strategy.analyze_transaction(test_tx)
                after = web3.eth.get_block('latest')['timestamp']
                total_time += (after - before)

            avg_latency = total_time / iterations
            latency_results[name] = avg_latency

        logger.info("Latency Optimization Results:")
        for strategy, latency in latency_results.items():
            logger.info(f"{strategy} Strategy Average Latency: {latency} seconds")

    @pytest.mark.asyncio
    async def test_gas_optimization(self, web3, config, arbitrage_strategy, jit_strategy, sandwich_strategy):
        """Test and optimize gas usage for all strategies."""
        strategies = {
            'arbitrage': arbitrage_strategy,
            'jit': jit_strategy,
            'sandwich': sandwich_strategy
        }

        gas_results = {}
        
        for name, strategy in strategies.items():
            # Create test transaction
            test_tx = {
                'hash': '0x' + '00' * 32,
                'to': config['dex']['uniswap_v2_router'],
                'value': web3.to_wei(10, 'ether'),
                'gasPrice': web3.to_wei(50, 'gwei'),
                'input': '0x38ed1739'
            }

            # Analyze opportunity and track gas usage
            opportunity = await strategy.analyze_transaction(test_tx)
            
            if opportunity:
                gas_results[name] = {
                    'gas_estimate': opportunity.get('gas_estimate', 0),
                    'gas_price': opportunity.get('gas_price', 0)
                }

        logger.info("Gas Optimization Results:")
        for strategy, gas_data in gas_results.items():
            total_gas_cost = gas_data['gas_estimate'] * gas_data['gas_price']
            logger.info(f"{strategy} Strategy:")
            logger.info(f"Gas Estimate: {gas_data['gas_estimate']}")
            logger.info(f"Gas Price: {gas_data['gas_price']} wei")
            logger.info(f"Total Gas Cost: {total_gas_cost} wei")
