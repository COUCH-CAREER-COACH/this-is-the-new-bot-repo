"""Simple tests for Enhanced Arbitrage Strategy V2."""
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock
from web3 import Web3

from src.arbitrage_strategy_v2 import EnhancedArbitrageStrategy
from src import mainnet_helpers as mainnet

@pytest.fixture
def web3_mock():
    """Create a mocked Web3 instance."""
    w3 = Mock(spec=Web3)
    w3.eth = Mock()
    w3.eth.chain_id = 1  # Mainnet
    w3.eth.gas_price = 50 * 10**9  # 50 GWEI
    w3.eth.get_code = Mock(return_value='0x123...')  # Non-empty code
    w3.is_address = Mock(return_value=True)
    w3.to_checksum_address = Mock(side_effect=lambda x: x)
    w3.to_wei = Mock(side_effect=lambda x, unit='ether': int(Decimal(x) * 10**18))
    return w3

@pytest.fixture
def config():
    """Create test configuration."""
    return {
        'dex': {
            'uniswap_v2_router': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
            'sushiswap_router': '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F'
        },
        'flash_loan': {
            'providers': {
                'aave': {
                    'pool_address_provider': '0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5'
                }
            }
        },
        'strategies': {
            'arbitrage': {
                'min_profit_wei': str(mainnet.MIN_PROFIT_THRESHOLD),
                'max_position_size': str(mainnet.MAX_POSITION_SIZE)
            }
        }
    }

@pytest.fixture
async def strategy(web3_mock, config):
    """Create arbitrage strategy instance."""
    strategy = EnhancedArbitrageStrategy(web3_mock, config)
    strategy._load_abi = Mock(return_value=[])  # Mock ABI loading
    strategy.dex_handler = Mock()
    strategy.dex_handler.decode_swap_data = Mock(return_value={
        'path': [
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
            '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'   # USDC
        ]
    })
    strategy.dex_handler.get_pool_info = AsyncMock(return_value={
        'pair_address': '0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc',
        'reserves': {
            'token0': '1000000000000',  # 1M USDC
            'token1': '1000000000000000000000'  # 1000 ETH
        },
        'fee': Decimal('0.003'),
        'block_timestamp_last': 1234567890
    })
    return strategy

@pytest.mark.asyncio
async def test_initialization(strategy):
    """Test strategy initialization."""
    assert strategy.min_profit_wei >= mainnet.MIN_PROFIT_THRESHOLD
    assert strategy.max_position_size <= mainnet.MAX_POSITION_SIZE
    assert len(strategy.contracts_to_check) == 4  # Flash loan, 2 routers, arb contract

@pytest.mark.asyncio
async def test_analyze_transaction_invalid_input(strategy):
    """Test handling of invalid transaction input."""
    assert await strategy.analyze_transaction(None) is None
    assert await strategy.analyze_transaction({}) is None
    assert await strategy.analyze_transaction({'invalid': 'data'}) is None

@pytest.mark.asyncio
async def test_analyze_transaction_valid_opportunity(strategy):
    """Test analysis of valid arbitrage opportunity."""
    tx = {
        'input': '0x38ed1739000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000002000000000000000000000000c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2000000000000000000000000a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
    }
    
    opportunity = await strategy.analyze_transaction(tx)
    
    assert opportunity is not None
    assert opportunity['type'] == 'arbitrage'
    assert 'amount' in opportunity
    assert 'profit' in opportunity
    assert opportunity['gas_price'] <= mainnet.MAX_GAS_PRICE

@pytest.mark.asyncio
async def test_execute_opportunity_success(strategy):
    """Test successful execution of arbitrage opportunity."""
    opportunity = {
        'type': 'arbitrage',
        'token_in': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
        'token_out': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'amount': str(mainnet.MIN_PROFIT_THRESHOLD * 10),
        'profit': str(mainnet.MIN_PROFIT_THRESHOLD * 2),
        'gas_price': 50 * 10**9,
        'pools': {
            'uniswap': '0x123...',
            'sushiswap': '0x456...'
        },
        'timestamp': 1234567890
    }
    
    strategy._execute_with_flash_loan = AsyncMock(return_value=(True, opportunity['profit']))
    
    success = await strategy.execute_opportunity(opportunity)
    assert success is True

@pytest.mark.asyncio
async def test_execute_opportunity_high_gas(strategy):
    """Test rejection of opportunity when gas price is too high."""
    opportunity = {
        'type': 'arbitrage',
        'token_in': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
        'token_out': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'amount': str(mainnet.MIN_PROFIT_THRESHOLD * 10),
        'profit': str(mainnet.MIN_PROFIT_THRESHOLD * 2),
        'gas_price': 1500 * 10**9,  # 1500 GWEI
        'pools': {
            'uniswap': '0x123...',
            'sushiswap': '0x456...'
        },
        'timestamp': 1234567890
    }
    
    success = await strategy.execute_opportunity(opportunity)
    assert success is False
