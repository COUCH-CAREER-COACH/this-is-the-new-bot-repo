"""Strategy Optimization Script"""
import asyncio
import time
import statistics
import os
from decimal import Decimal
from typing import Dict, List
import matplotlib.pyplot as plt
import numpy as np
from web3 import Web3
from eth_utils import to_checksum_address
from unittest.mock import Mock, AsyncMock, patch

from src.strategies.sandwich_v3 import SandwichStrategyV3
from src.strategies.frontrun_v3 import FrontrunStrategyV3
from src.strategies.jit_v3 import JITLiquidityStrategyV3
from test.mock_flash_loan_v5 import MockFlashLoan

# Constants
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5A6f"

async def create_mock_strategy():
    """Create a mock strategy for testing"""
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
         patch('src.strategies.sandwich_v3.DEXHandler', return_value=dex_handler):
        strategy = SandwichStrategyV3(web3, config)
        strategy.web3 = web3
        strategy.dex_handler = dex_handler
        strategy.flash_loan = flash_loan
        return strategy

async def test_strategy():
    """Test strategy performance"""
    strategy = await create_mock_strategy()
    
    # Create test transaction
    tx = {
        'hash': '0x1234567890123456789012345678901234567890123456789012345678901234',
        'to': ROUTER,
        'value': Web3.to_wei(5, 'ether'),
        'gasPrice': Web3.to_wei(50, 'gwei')
    }
    
    # Test analysis latency
    start = time.perf_counter()
    await strategy.analyze_transaction(tx)
    end = time.perf_counter()
    latency = (end - start) * 1000  # Convert to milliseconds
    
    print(f"\nStrategy Analysis Results:")
    print(f"Latency: {latency:.2f}ms")

async def main():
    """Main function"""
    await test_strategy()

if __name__ == "__main__":
    asyncio.run(main())
