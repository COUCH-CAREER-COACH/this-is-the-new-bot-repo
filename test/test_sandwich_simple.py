"""Simple test suite for sandwich attack execution"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from web3 import Web3
from eth_utils import to_checksum_address

from src.strategies.sandwich_v3 import SandwichStrategyV3
from test.mock_loans import MockFlashLoan

# Constants
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"

@pytest.fixture
async def mock_strategy():
    """Create sandwich strategy with mocks"""
    # Mock web3
    web3 = Mock()
    web3.eth = Mock()
    web3.eth.get_block = AsyncMock(return_value={'baseFeePerGas': Web3.to_wei(30, 'gwei')})
    web3.eth.get_transaction_count = AsyncMock(return_value=1)
    web3.eth.wait_for_transaction_receipt = AsyncMock(return_value={'status': 1})
    
    # Mock contract
    mock_contract = Mock()
    mock_contract.functions = Mock()
    mock_contract.address = ROUTER
    web3.eth.contract = Mock(return_value=mock_contract)
    
    # Mock DEX handler
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
    
    config = {
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
            'uniswap_v2_factory': '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f'
        },
        'flash_loan': {
            'preferred_provider': 'aave',
            'providers': {
                'aave': {
                    'pool_address_provider': to_checksum_address('0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5'),
                    'fee': '0.0009'
                }
            }
        },
        'contracts': {
            'arbitrage_contract': to_checksum_address('0x1234567890123456789012345678901234567890')
        }
    }
    
    with patch('src.base_strategy.FlashLoan', MockFlashLoan), \
         patch('src.strategies.sandwich_v3.DEXHandler', return_value=dex_handler):
        strategy = SandwichStrategyV3(web3, config)
        strategy.web3 = web3
        strategy.dex_handler = dex_handler
        return strategy

@pytest.mark.asyncio
async def test_execute_sandwich_attack(mock_strategy):
    """Test execution of sandwich attack"""
    # Create a sandwich opportunity
    opportunity = {
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
    }
    
    # Execute the sandwich attack
    success = await mock_strategy.execute_opportunity(opportunity)
    
    assert success, "Sandwich attack execution should succeed"
