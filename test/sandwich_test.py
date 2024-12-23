"""Test suite for sandwich strategy"""
import pytest
import asyncio
import time
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from web3 import Web3
from eth_utils import to_checksum_address

from src.sandwich_strategy_new import EnhancedSandwichStrategy
from test.mock_loans import MockFlashLoan

# Constants
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"

@pytest.fixture
def web3():
    """Create mock Web3 instance"""
    mock_web3 = Mock()
    mock_web3.eth = Mock()
    mock_web3.eth.get_block = AsyncMock(return_value={
        'baseFeePerGas': Web3.to_wei(30, 'gwei'),
        'timestamp': int(time.time()),
        'transactions': [f"0x{'1'*64}" for _ in range(100)],
        'gasUsed': 12000000,
        'gasLimit': 15000000
    })
    mock_web3.eth.get_transaction = AsyncMock(return_value={
        'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
        'maxFeePerGas': Web3.to_wei(100, 'gwei'),
        'gasPrice': Web3.to_wei(50, 'gwei')
    })
    mock_web3.to_wei = Web3.to_wei
    mock_web3.from_wei = Web3.from_wei
    
    # Mock contract
    mock_contract = Mock()
    mock_contract.address = ROUTER
    mock_contract.functions = Mock()
    mock_web3.eth.contract = Mock(return_value=mock_contract)
    
    return mock_web3

@pytest.fixture
def dex_handler():
    """Create mock DEX handler"""
    mock_handler = Mock()
    
    # Mock pool data
    pool_data = {
        'pair_address': to_checksum_address('0x1234567890123456789012345678901234567890'),
        'reserves': {
            'token0': Web3.to_wei(10000, 'ether'),
            'token1': Web3.to_wei(20000000, 'ether')
        },
        'fee': Decimal('0.003'),
        'token0': WETH,
        'token1': DAI,
        'decimals0': 18,
        'decimals1': 18,
        'block_timestamp_last': int(time.time())
    }
    
    # Mock swap data
    swap_data = {
        'dex': 'uniswap',
        'path': [WETH, DAI],
        'amountIn': Web3.to_wei(5, 'ether'),
        'method': 'swapExactTokensForTokens'
    }
    
    mock_handler.decode_swap_data = Mock(return_value=swap_data)
    mock_handler.get_pool_info = AsyncMock(return_value=pool_data)
    mock_handler.calculate_price_impact = Mock(return_value=Decimal('0.01'))
    
    def update_pool_reserves(token0_reserve: int, token1_reserve: int):
        """Update pool reserves for testing"""
        new_pool_data = pool_data.copy()
        new_pool_data['reserves'] = {
            'token0': Web3.to_wei(token0_reserve, 'ether'),
            'token1': Web3.to_wei(token1_reserve, 'ether')
        }
        mock_handler.get_pool_info.return_value = new_pool_data
        
    mock_handler.update_pool_reserves = update_pool_reserves
    return mock_handler

@pytest.fixture
def config():
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
            'uniswap_v2_router': ROUTER,
            'uniswap_v2_factory': '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f',
            'uniswap_init_code_hash': "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f"
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
            'arbitrage_contract': '0x1234567890123456789012345678901234567890'
        }
    }

@pytest.fixture
def strategy(web3, config, dex_handler):
    """Create sandwich strategy with mocks"""
    with patch('src.base_strategy.FlashLoan', MockFlashLoan), \
         patch('src.sandwich_strategy_new.DEXHandler', return_value=dex_handler), \
         patch('src.utils.web3_utils.validate_address', side_effect=lambda _, x: x if isinstance(x, str) else x.address):
        strategy = EnhancedSandwichStrategy(web3, config)
        strategy.web3 = web3  # Ensure web3 instance is properly set
        strategy.dex_handler = dex_handler
        return strategy

@pytest.mark.asyncio
async def test_analyze_profitable_sandwich(strategy):
    """Test profitable sandwich opportunity analysis"""
    victim_tx = {
        'hash': '0x123',
        'to': ROUTER,
        'value': Web3.to_wei(5, 'ether'),
        'gasPrice': Web3.to_wei(35, 'gwei')
    }

    result = await strategy.analyze_transaction(victim_tx)

    assert result is not None, "Should identify profitable opportunity"
    assert result['type'] == 'sandwich'
    assert result['token_in'] == WETH
    assert result['token_out'] == DAI
    assert result['frontrun_amount'] > 0
    assert result['backrun_amount'] > 0
    assert result['expected_profit'] > strategy.min_profit_wei

@pytest.mark.asyncio
async def test_analyze_high_price_impact(strategy):
    """Test rejection of high price impact opportunity"""
    victim_tx = {
        'hash': '0x123',
        'to': ROUTER,
        'value': Web3.to_wei(100, 'ether'),
        'gasPrice': Web3.to_wei(120, 'gwei')
    }

    # Update pool with limited liquidity
    strategy.dex_handler.update_pool_reserves(200, 400000)  # 200 ETH, 400K DAI
    strategy.dex_handler.calculate_price_impact.return_value = Decimal('0.05')  # 5% impact

    result = await strategy.analyze_transaction(victim_tx)
    assert result is None, "Should reject high price impact opportunity"
