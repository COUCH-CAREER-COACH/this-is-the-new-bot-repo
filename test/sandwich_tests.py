"""Test suite for sandwich strategy implementation"""
import pytest
import asyncio
import time
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from web3 import Web3
from eth_utils import to_checksum_address

from src.sandwich_strategy_new import EnhancedSandwichStrategy
from test.mock_loans import MockFlashLoan
from test.mock_dex import MockWeb3, MockDexHandler

# Constants
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
UNISWAP_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
UNISWAP_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
UNISWAP_INIT_CODE_HASH = "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f"

def create_test_config():
    """Create test configuration"""
    return {
        'strategies': {
            'sandwich': {
                'min_profit_wei': Web3.to_wei(0.05, 'ether'),
                'max_position_size': Web3.to_wei(50, 'ether'),
                'max_price_impact': '0.03',
                'min_liquidity': Web3.to_wei(100, 'ether'),
                'max_gas_price': Web3.to_wei(300, 'gwei')
            }
        },
        'dex': {
            'uniswap_v2_router': UNISWAP_ROUTER,
            'uniswap_v2_factory': UNISWAP_FACTORY,
            'uniswap_init_code_hash': UNISWAP_INIT_CODE_HASH
        },
        'flash_loan': {
            'preferred_provider': 'aave',
            'providers': {
                'aave': {
                    'pool_address_provider': '0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5',
                    'fee': '0.0009'
                }
            }
        },
        'contracts': {
            'arbitrage_contract': to_checksum_address('0x1234567890123456789012345678901234567890')
        }
    }

def create_mock_web3():
    """Create mock Web3 instance"""
    mock_web3 = MockWeb3()
    mock_web3.eth.get_block = AsyncMock(return_value={
        'baseFeePerGas': Web3.to_wei(30, 'gwei'),
        'timestamp': int(time.time()),
        'transactions': [f"0x{'1'*64}" for _ in range(100)],
        'gasUsed': 12000000,
        'gasLimit': 15000000
    })
    return mock_web3

def create_mock_dex_handler():
    """Create mock DEX handler"""
    handler = MockDexHandler()
    handler.update_pool_reserves(10000, 20000000)  # 10K ETH, 20M DAI
    handler.calculate_price_impact.return_value = Decimal('0.01')  # 1% impact
    return handler

@pytest.fixture
async def strategy():
    """Create sandwich strategy with mocks"""
    config = create_test_config()
    web3 = create_mock_web3()
    dex_handler = create_mock_dex_handler()
    
    with patch('src.base_strategy.FlashLoan', MockFlashLoan), \
         patch('src.sandwich_strategy_new.DEXHandler', return_value=dex_handler):
        strategy = EnhancedSandwichStrategy(web3, config)
        yield strategy

@pytest.mark.asyncio
async def test_analyze_profitable_sandwich(strategy):
    """Test profitable sandwich opportunity analysis"""
    # Setup test data
    victim_tx = {
        'hash': '0x123',
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(5, 'ether'),
        'gasPrice': Web3.to_wei(35, 'gwei')
    }

    result = await strategy.analyze_transaction(victim_tx)

    assert result is not None, "Should identify profitable opportunity"
    assert result['type'] == 'sandwich'
    assert result['frontrun_amount'] > 0
    assert result['backrun_amount'] > 0
    assert result['expected_profit'] > strategy.min_profit_wei

@pytest.mark.asyncio
async def test_analyze_high_price_impact(strategy):
    """Test rejection of high price impact opportunity"""
    # Setup test data
    victim_tx = {
        'hash': '0x123',
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(100, 'ether'),
        'gasPrice': Web3.to_wei(120, 'gwei')
    }

    # Update pool with limited liquidity
    strategy.dex_handler.update_pool_reserves(200, 400000)  # 200 ETH, 400K DAI
    strategy.dex_handler.calculate_price_impact.return_value = Decimal('0.05')  # 5% impact

    result = await strategy.analyze_transaction(victim_tx)
    assert result is None, "Should reject opportunity with high price impact"
