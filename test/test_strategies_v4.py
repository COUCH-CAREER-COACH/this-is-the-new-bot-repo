"""Test suite for all MEV strategies"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from web3 import Web3
from eth_utils import to_checksum_address

from src.strategies.sandwich_v3 import SandwichStrategyV3
from src.strategies.frontrun_v3 import FrontrunStrategyV3
from src.strategies.jit_v3 import JITLiquidityStrategyV3
from test.mock_flash_loan_v4 import MockFlashLoan

# Constants
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"

def create_mock_web3():
    """Create mock Web3 instance"""
    web3 = Mock()
    web3.eth = Mock()
    web3.eth.get_block = AsyncMock(return_value={'baseFeePerGas': Web3.to_wei(30, 'gwei')})
    web3.eth.get_transaction_count = AsyncMock(return_value=1)
    web3.eth.wait_for_transaction_receipt = AsyncMock(return_value={'status': 1})
    web3.eth.gas_price = Web3.to_wei(50, 'gwei')
    
    # Mock contract
    mock_contract = Mock()
    mock_contract.functions = Mock()
    mock_contract.address = ROUTER
    mock_contract.functions.factory = Mock(return_value=Mock(call=Mock(return_value=FACTORY)))
    mock_contract.functions.allPairsLength = Mock(return_value=Mock(call=Mock(return_value=100)))
    
    # Mock swap function
    mock_contract.functions.swapExactTokensForTokens = Mock(return_value=Mock(
        build_transaction=Mock(return_value={
            'gas': 200000,
            'maxFeePerGas': Web3.to_wei(100, 'gwei'),
            'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
            'nonce': 1
        })
    ))
    
    # Mock liquidity functions
    mock_contract.functions.addLiquidity = Mock(return_value=Mock(
        build_transaction=Mock(return_value={
            'gas': 200000,
            'maxFeePerGas': Web3.to_wei(100, 'gwei'),
            'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
            'nonce': 1
        })
    ))
    
    mock_contract.functions.removeLiquidity = Mock(return_value=Mock(
        build_transaction=Mock(return_value={
            'gas': 150000,
            'maxFeePerGas': Web3.to_wei(100, 'gwei'),
            'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
            'nonce': 2
        })
    ))
    
    web3.eth.contract = Mock(return_value=mock_contract)
    return web3

def create_mock_dex_handler():
    """Create mock DEX handler"""
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
    
    # Mock optimal liquidity calculation
    dex_handler.calculate_optimal_liquidity = Mock(return_value=(
        Web3.to_wei(2, 'ether'),  # optimal ETH amount
        Web3.to_wei(4000, 'ether')  # optimal DAI amount
    ))
    
    return dex_handler

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
            },
            'frontrun': {
                'min_profit_wei': Web3.to_wei(0.05, 'ether'),
                'max_position_size': Web3.to_wei(50, 'ether'),
                'max_price_impact': '0.03',
                'min_liquidity': Web3.to_wei(100, 'ether'),
                'max_gas_price': Web3.to_wei(300, 'gwei')
            },
            'jit': {
                'min_profit_wei': Web3.to_wei(0.05, 'ether'),
                'max_position_size': Web3.to_wei(50, 'ether'),
                'max_price_impact': '0.03',
                'min_liquidity': Web3.to_wei(100, 'ether'),
                'max_gas_price': Web3.to_wei(300, 'gwei'),
                'liquidity_hold_blocks': 2
            }
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
        },
        'contracts': {
            'arbitrage_contract': to_checksum_address('0x1234567890123456789012345678901234567890')
        }
    }

@pytest.fixture
async def sandwich_strategy():
    """Create sandwich strategy with mocks"""
    web3 = create_mock_web3()
    config = create_test_config()
    dex_handler = create_mock_dex_handler()
    flash_loan = MockFlashLoan(web3, config)
    
    with patch('src.base_strategy.FlashLoan', return_value=flash_loan), \
         patch('src.strategies.sandwich_v3.DEXHandler', return_value=dex_handler):
        strategy = SandwichStrategyV3(web3, config)
        strategy.web3 = web3
        strategy.dex_handler = dex_handler
        strategy.flash_loan = flash_loan
        return strategy

@pytest.fixture
async def frontrun_strategy():
    """Create frontrun strategy with mocks"""
    web3 = create_mock_web3()
    config = create_test_config()
    dex_handler = create_mock_dex_handler()
    flash_loan = MockFlashLoan(web3, config)
    
    with patch('src.base_strategy.FlashLoan', return_value=flash_loan), \
         patch('src.strategies.frontrun_v3.DEXHandler', return_value=dex_handler):
        strategy = FrontrunStrategyV3(web3, config)
        strategy.web3 = web3
        strategy.dex_handler = dex_handler
        strategy.flash_loan = flash_loan
        return strategy

@pytest.fixture
async def jit_strategy():
    """Create JIT strategy with mocks"""
    web3 = create_mock_web3()
    config = create_test_config()
    dex_handler = create_mock_dex_handler()
    flash_loan = MockFlashLoan(web3, config)
    
    with patch('src.base_strategy.FlashLoan', return_value=flash_loan), \
         patch('src.strategies.jit_v3.DEXHandler', return_value=dex_handler):
        strategy = JITLiquidityStrategyV3(web3, config)
        strategy.web3 = web3
        strategy.dex_handler = dex_handler
        strategy.flash_loan = flash_loan
        return strategy

@pytest.mark.asyncio
async def test_sandwich_attack(sandwich_strategy):
    """Test execution of sandwich attack"""
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
    
    success = await sandwich_strategy.execute_opportunity(opportunity)
    assert success, "Sandwich attack execution should succeed"
    assert sandwich_strategy.flash_loan.execute_flash_loan.called, "Flash loan should be executed"

@pytest.mark.asyncio
async def test_frontrun_attack(frontrun_strategy):
    """Test execution of frontrun attack"""
    opportunity = {
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
    }
    
    success = await frontrun_strategy.execute_opportunity(opportunity)
    assert success, "Frontrun attack execution should succeed"
    assert frontrun_strategy.flash_loan.execute_flash_loan.called, "Flash loan should be executed"

@pytest.mark.asyncio
async def test_jit_strategy(jit_strategy):
    """Test execution of JIT liquidity strategy"""
    opportunity = {
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
    
    success = await jit_strategy.execute_opportunity(opportunity)
    assert success, "JIT liquidity strategy execution should succeed"
    assert jit_strategy.flash_loan.execute_flash_loan.called, "Flash loan should be executed"
