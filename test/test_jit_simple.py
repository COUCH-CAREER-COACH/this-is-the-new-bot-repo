"""Simple test suite for JIT liquidity strategy execution"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from web3 import Web3
from eth_utils import to_checksum_address

from src.strategies.jit_v3 import JITLiquidityStrategyV3
from test.mock_loans import MockFlashLoan

# Constants
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"

@pytest.fixture
async def mock_strategy():
    """Create JIT liquidity strategy with mocks"""
    # Mock web3
    web3 = Mock()
    web3.eth = Mock()
    web3.eth.get_block = AsyncMock(return_value={'baseFeePerGas': Web3.to_wei(30, 'gwei')})
    web3.eth.get_transaction_count = AsyncMock(return_value=1)
    web3.eth.wait_for_transaction_receipt = AsyncMock(return_value={'status': 1})
    
    # Mock contract calls
    mock_contract = Mock()
    mock_contract.functions = Mock()
    mock_contract.address = ROUTER
    
    # Mock addLiquidity function
    mock_contract.functions.addLiquidity = Mock(return_value=Mock(
        build_transaction=Mock(return_value={
            'gas': 200000,
            'maxFeePerGas': Web3.to_wei(100, 'gwei'),
            'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
            'nonce': 1
        })
    ))
    
    # Mock removeLiquidity function
    mock_contract.functions.removeLiquidity = Mock(return_value=Mock(
        build_transaction=Mock(return_value={
            'gas': 150000,
            'maxFeePerGas': Web3.to_wei(100, 'gwei'),
            'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
            'nonce': 2
        })
    ))
    
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
    
    # Mock optimal liquidity calculation
    dex_handler.calculate_optimal_liquidity = Mock(return_value=(
        Web3.to_wei(2, 'ether'),  # optimal ETH amount
        Web3.to_wei(4000, 'ether')  # optimal DAI amount
    ))
    
    config = {
        'strategies': {
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
    
    with patch('src.base_strategy.FlashLoan', MockFlashLoan), \
         patch('src.strategies.jit_v3.DEXHandler', return_value=dex_handler):
        strategy = JITLiquidityStrategyV3(web3, config)
        strategy.web3 = web3
        strategy.dex_handler = dex_handler
        return strategy

@pytest.mark.asyncio
async def test_execute_jit_strategy(mock_strategy):
    """Test execution of JIT liquidity strategy"""
    # Create a JIT opportunity
    opportunity = {
        'type': 'jit',
        'dex': 'uniswap',
        'token_a': WETH,
        'token_b': DAI,
        'amount_a': Web3.to_wei(2, 'ether'),  # ETH amount to provide
        'amount_b': Web3.to_wei(4000, 'ether'),  # DAI amount to provide
        'target_tx_hash': '0x1234567890123456789012345678901234567890123456789012345678901234',
        'pool_address': to_checksum_address('0x1234567890123456789012345678901234567890'),
        'gas_price': Web3.to_wei(50, 'gwei'),
        'expected_profit': Web3.to_wei(0.1, 'ether'),
        'hold_blocks': 2  # Number of blocks to hold liquidity
    }
    
    # Execute the JIT strategy
    success = await mock_strategy.execute_opportunity(opportunity)
    
    assert success, "JIT liquidity strategy execution should succeed"
    
    # Verify flash loan execution
    assert mock_strategy.flash_loan.execute.called, "Flash loan should be executed"
    
    # Verify the callback data encoding
    callback_args = mock_strategy.flash_loan.execute.call_args[0]
    assert callback_args[0] == WETH, "Flash loan token should be WETH"
    assert callback_args[1] == opportunity['amount_a'], "Flash loan amount should match ETH liquidity amount"
    
    # Verify gas price optimization
    tx_data = mock_strategy.flash_loan.execute.call_args[1].get('tx_params', {})
    assert tx_data.get('maxFeePerGas') == opportunity['gas_price'], "Should use optimal gas price"
