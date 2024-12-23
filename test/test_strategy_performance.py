"""Performance test suite for MEV strategies"""
import pytest
import time
import asyncio
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from web3 import Web3
from eth_utils import to_checksum_address
import statistics

from src.strategies.sandwich_v3 import SandwichStrategyV3
from src.strategies.frontrun_v3 import FrontrunStrategyV3
from src.strategies.jit_v3 import JITLiquidityStrategyV3
from test.mock_flash_loan_v5 import MockFlashLoan

# Constants
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"

# Test configurations
NUM_ITERATIONS = 100  # Number of iterations for each test
LATENCY_THRESHOLD_MS = 50  # Maximum acceptable latency in milliseconds

def create_test_tx(amount: int = None) -> dict:
    """Create a test transaction with random amount if none provided"""
    if amount is None:
        amount = Web3.to_wei(1 + (time.time() % 10), 'ether')  # Random amount between 1-10 ETH
    return {
        'hash': '0x1234567890123456789012345678901234567890123456789012345678901234',
        'to': ROUTER,
        'value': amount,
        'gasPrice': Web3.to_wei(50, 'gwei')
    }

@pytest.fixture
async def strategies():
    """Create all strategies with mocks"""
    web3 = Mock()
    web3.eth = Mock()
    web3.eth.get_block = AsyncMock(return_value={'baseFeePerGas': Web3.to_wei(30, 'gwei')})
    web3.eth.get_transaction_count = AsyncMock(return_value=1)
    web3.eth.wait_for_transaction_receipt = AsyncMock(return_value={'status': 1})
    web3.eth.gas_price = Web3.to_wei(50, 'gwei')
    
    config = {
        'strategies': {
            'sandwich': {'min_profit_wei': Web3.to_wei(0.05, 'ether')},
            'frontrun': {'min_profit_wei': Web3.to_wei(0.05, 'ether')},
            'jit': {'min_profit_wei': Web3.to_wei(0.05, 'ether')}
        },
        'dex': {
            'uniswap_v2_router': ROUTER,
            'uniswap_v2_factory': FACTORY
        },
        'flash_loan': {
            'preferred_provider': 'aave',
            'providers': {
                'aave': {
                    'pool_address_provider': to_checksum_address('0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5'),
                    'fee': '0.0009'
                }
            }
        }
    }
    
    dex_handler = Mock()
    dex_handler.get_pool_info = AsyncMock(return_value={
        'pair_address': to_checksum_address('0x1234567890123456789012345678901234567890'),
        'reserves': {
            'token0': Web3.to_wei(10000, 'ether'),
            'token1': Web3.to_wei(20000000, 'ether')
        },
        'fee': Decimal('0.003'),
        'token0': WETH,
        'token1': DAI,
        'decimals0': 18,
        'decimals1': 18
    })
    
    flash_loan = MockFlashLoan(web3, config)
    
    with patch('src.base_strategy.FlashLoan', return_value=flash_loan), \
         patch('src.strategies.sandwich_v3.DEXHandler', return_value=dex_handler), \
         patch('src.strategies.frontrun_v3.DEXHandler', return_value=dex_handler), \
         patch('src.strategies.jit_v3.DEXHandler', return_value=dex_handler):
        
        sandwich = SandwichStrategyV3(web3, config)
        sandwich.web3 = web3
        sandwich.dex_handler = dex_handler
        sandwich.flash_loan = flash_loan
        
        frontrun = FrontrunStrategyV3(web3, config)
        frontrun.web3 = web3
        frontrun.dex_handler = dex_handler
        frontrun.flash_loan = flash_loan
        
        jit = JITLiquidityStrategyV3(web3, config)
        jit.web3 = web3
        jit.dex_handler = dex_handler
        jit.flash_loan = flash_loan
        
        return {
            'sandwich': sandwich,
            'frontrun': frontrun,
            'jit': jit
        }

@pytest.mark.asyncio
async def test_strategy_latency(strategies):
    """Test latency of each strategy's analysis phase"""
    results = {
        'sandwich': [],
        'frontrun': [],
        'jit': []
    }
    
    for _ in range(NUM_ITERATIONS):
        tx = create_test_tx()
        
        # Test sandwich strategy
        start = time.perf_counter()
        await strategies['sandwich'].analyze_transaction(tx)
        end = time.perf_counter()
        results['sandwich'].append((end - start) * 1000)  # Convert to milliseconds
        
        # Test frontrun strategy
        start = time.perf_counter()
        await strategies['frontrun'].analyze_transaction(tx)
        end = time.perf_counter()
        results['frontrun'].append((end - start) * 1000)
        
        # Test JIT strategy
        start = time.perf_counter()
        await strategies['jit'].analyze_transaction(tx)
        end = time.perf_counter()
        results['jit'].append((end - start) * 1000)
    
    # Calculate and report statistics
    for strategy, latencies in results.items():
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        
        print(f"\n{strategy.upper()} Strategy Latency Stats:")
        print(f"Average: {avg_latency:.2f}ms")
        print(f"95th percentile: {p95_latency:.2f}ms")
        print(f"99th percentile: {p99_latency:.2f}ms")
        
        assert avg_latency < LATENCY_THRESHOLD_MS, f"{strategy} average latency too high"
        assert p95_latency < LATENCY_THRESHOLD_MS * 1.5, f"{strategy} P95 latency too high"
        assert p99_latency < LATENCY_THRESHOLD_MS * 2, f"{strategy} P99 latency too high"

@pytest.mark.asyncio
async def test_concurrent_analysis(strategies):
    """Test strategy performance under concurrent load"""
    NUM_CONCURRENT = 10  # Number of concurrent transactions to analyze
    
    async def analyze_batch(strategy, txs):
        start = time.perf_counter()
        await asyncio.gather(*[strategy.analyze_transaction(tx) for tx in txs])
        end = time.perf_counter()
        return (end - start) * 1000  # Return total time in milliseconds
    
    results = {
        'sandwich': [],
        'frontrun': [],
        'jit': []
    }
    
    for _ in range(NUM_ITERATIONS // NUM_CONCURRENT):
        txs = [create_test_tx() for _ in range(NUM_CONCURRENT)]
        
        for strategy_name, strategy in strategies.items():
            batch_time = await analyze_batch(strategy, txs)
            results[strategy_name].append(batch_time / NUM_CONCURRENT)  # Average time per transaction
    
    # Calculate and report statistics
    for strategy, latencies in results.items():
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]
        
        print(f"\n{strategy.upper()} Concurrent Analysis Stats:")
        print(f"Average latency per tx: {avg_latency:.2f}ms")
        print(f"95th percentile: {p95_latency:.2f}ms")
        
        # Allow slightly higher latency for concurrent operations
        assert avg_latency < LATENCY_THRESHOLD_MS * 1.2, f"{strategy} concurrent average latency too high"
        assert p95_latency < LATENCY_THRESHOLD_MS * 1.8, f"{strategy} concurrent P95 latency too high"

@pytest.mark.asyncio
async def test_execution_speed(strategies):
    """Test execution speed of each strategy"""
    results = {
        'sandwich': [],
        'frontrun': [],
        'jit': []
    }
    
    opportunities = {
        'sandwich': {
            'type': 'sandwich',
            'dex': 'uniswap',
            'token_in': WETH,
            'token_out': DAI,
            'victim_amount': Web3.to_wei(5, 'ether'),
            'frontrun_amount': Web3.to_wei(2, 'ether'),
            'backrun_amount': Web3.to_wei(1.9, 'ether'),
            'pool_address': to_checksum_address('0x1234567890123456789012345678901234567890'),
            'gas_price': Web3.to_wei(50, 'gwei'),
            'expected_profit': Web3.to_wei(0.1, 'ether')
        },
        'frontrun': {
            'type': 'frontrun',
            'dex': 'uniswap',
            'token_in': WETH,
            'token_out': DAI,
            'target_amount': Web3.to_wei(5, 'ether'),
            'frontrun_amount': Web3.to_wei(2, 'ether'),
            'pool_address': to_checksum_address('0x1234567890123456789012345678901234567890'),
            'gas_price': Web3.to_wei(50, 'gwei'),
            'expected_profit': Web3.to_wei(0.1, 'ether'),
            'target_tx_hash': '0x1234567890123456789012345678901234567890123456789012345678901234'
        },
        'jit': {
            'type': 'jit',
            'dex': 'uniswap',
            'token_a': WETH,
            'token_b': DAI,
            'amount_a': Web3.to_wei(2, 'ether'),
            'amount_b': Web3.to_wei(4000, 'ether'),
            'target_tx_hash': '0x1234567890123456789012345678901234567890123456789012345678901234',
            'pool_address': to_checksum_address('0x1234567890123456789012345678901234567890'),
            'gas_price': Web3.to_wei(50, 'gwei'),
            'expected_profit': Web3.to_wei(0.1, 'ether'),
            'hold_blocks': 2
        }
    }
    
    for _ in range(NUM_ITERATIONS):
        for strategy_name, strategy in strategies.items():
            start = time.perf_counter()
            await strategy.execute_opportunity(opportunities[strategy_name])
            end = time.perf_counter()
            results[strategy_name].append((end - start) * 1000)
    
    # Calculate and report statistics
    for strategy, latencies in results.items():
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]
        
        print(f"\n{strategy.upper()} Execution Speed Stats:")
        print(f"Average execution time: {avg_latency:.2f}ms")
        print(f"95th percentile: {p95_latency:.2f}ms")
        
        # Execution can take longer than analysis
        assert avg_latency < LATENCY_THRESHOLD_MS * 2, f"{strategy} average execution time too high"
        assert p95_latency < LATENCY_THRESHOLD_MS * 3, f"{strategy} P95 execution time too high"
