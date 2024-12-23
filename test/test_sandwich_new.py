"""Test suite for sandwich strategy implementation with realistic mainnet conditions"""
import pytest
import asyncio
import time
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from web3 import Web3
from eth_utils import to_checksum_address

from src.sandwich_strategy_new import EnhancedSandwichStrategy
from src.mock_flash_loan import MockFlashLoan
from test.mocks import MockWeb3, MockDexHandler

# Constants for testing with real mainnet addresses
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI_ADDRESS = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
UNISWAP_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"

# Mainnet init code hashes
UNISWAP_INIT_CODE_HASH = "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f"
SUSHISWAP_INIT_CODE_HASH = "0xe18a34eb0e04b04f7a0ac29a6e80748dca96319b42c54d679cb821dca90c6303"

@pytest.fixture
async def setup_strategy():
    """Setup sandwich strategy with mocked dependencies and realistic conditions"""
    w3 = MockWeb3()
    dex_handler = MockDexHandler()
    
    # Realistic configuration with mainnet addresses and parameters
    config = {
        'strategies': {
            'sandwich': {
                'min_profit_wei': Web3.to_wei(0.05, 'ether'),  # 0.05 ETH min profit
                'max_position_size': Web3.to_wei(50, 'ether'),  # 50 ETH max position
                'max_price_impact': '0.03',  # 3% max price impact
                'min_liquidity': Web3.to_wei(100, 'ether'),  # Min pool liquidity
                'max_gas_price': Web3.to_wei(300, 'gwei'),  # Max gas price
                'competition_factor': '1.2'  # Competition adjustment
            }
        },
        'dex': {
            'uniswap_v2_router': UNISWAP_ROUTER,
            'uniswap_v2_factory': '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f',
            'sushiswap_router': '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',
            'sushiswap_factory': '0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac',
            'uniswap_init_code_hash': UNISWAP_INIT_CODE_HASH,
            'sushiswap_init_code_hash': SUSHISWAP_INIT_CODE_HASH
        },
        'flash_loan': {
            'preferred_provider': 'aave',
            'providers': {
                'aave': {
                    'pool_address_provider': '0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5',
                    'fee': '0.0009'
                },
                'balancer': {
                    'vault': '0xBA12222222228d8Ba445958a75a0704d566BF2C8',
                    'fee': '0.0001'
                }
            }
        },
        'contracts': {
            'arbitrage_contract': to_checksum_address('0x1234567890123456789012345678901234567890')
        },
        'gas_limits': {
            'sandwich_frontrun': 300000,
            'sandwich_backrun': 300000
        }
    }

    # Initialize strategy with mocked components
    with patch('src.base_strategy.FlashLoan', MockFlashLoan), \
         patch('src.sandwich_strategy_new.DEXHandler', return_value=dex_handler):
        strategy = EnhancedSandwichStrategy(w3, config)
        await dex_handler.setup_realistic_pool()
        yield strategy

@pytest.fixture(autouse=True)
async def setup_and_cleanup():
    """Setup and cleanup for each test"""
    yield
    await asyncio.sleep(0)  # Allow any pending tasks to complete

@pytest.mark.asyncio
async def test_analyze_profitable_sandwich(setup_strategy):
    """Test analysis of a profitable sandwich opportunity with realistic mainnet conditions"""
    strategy = await setup_strategy
    
    # Mock victim transaction with realistic parameters
    victim_tx = {
        'hash': '0x123',
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(5, 'ether'),  # 5 ETH - realistic trade size
        'gasPrice': Web3.to_wei(35, 'gwei'),
        'maxFeePerGas': Web3.to_wei(40, 'gwei'),
        'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
        'nonce': 100,
        'blockNumber': 17000000
    }

    # Mock swap data
    swap_data = {
        'dex': 'uniswap',
        'path': [WETH_ADDRESS, DAI_ADDRESS],
        'amountIn': Web3.to_wei(5, 'ether')
    }

    strategy.dex_handler.decode_swap_data.return_value = swap_data

    result = await strategy.analyze_transaction(victim_tx)

    assert result is not None, "Should identify profitable opportunity"
    assert result['type'] == 'sandwich'
    assert result['token_in'] == swap_data['path'][0]
    assert result['token_out'] == swap_data['path'][1]
    assert result['victim_amount'] == swap_data['amountIn']
    assert result['frontrun_amount'] > 0
    assert result['backrun_amount'] > 0
    assert result['expected_profit'] > strategy.min_profit_wei

@pytest.mark.asyncio
async def test_analyze_high_price_impact(setup_strategy):
    """Test rejection of sandwich with high price impact in realistic conditions"""
    strategy = await setup_strategy
    
    # Mock network congestion
    strategy.w3.eth.get_block = AsyncMock(return_value={
        'baseFeePerGas': Web3.to_wei(100, 'gwei'),  # High base fee during congestion
        'timestamp': int(time.time()),
        'transactions': ['0x123'] * 100,  # Many pending txs
        'gasUsed': 14500000,  # Nearly full block
        'gasLimit': 15000000
    })

    # Mock victim transaction with large amount
    victim_tx = {
        'hash': '0x123',
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(100, 'ether'),  # 100 ETH - very large trade
        'gasPrice': Web3.to_wei(120, 'gwei'),
        'maxFeePerGas': Web3.to_wei(150, 'gwei'),
        'maxPriorityFeePerGas': Web3.to_wei(20, 'gwei')
    }

    # Setup pool with limited liquidity
    await strategy.dex_handler.setup_realistic_pool(
        token0_reserve=200,  # 200 ETH
        token1_reserve=400000  # 400K DAI
    )

    swap_data = {
        'dex': 'uniswap',
        'path': [WETH_ADDRESS, DAI_ADDRESS],
        'amountIn': Web3.to_wei(100, 'ether')
    }

    strategy.dex_handler.decode_swap_data.return_value = swap_data

    result = await strategy.analyze_transaction(victim_tx)
    assert result is None, "Should reject opportunity with high price impact"
