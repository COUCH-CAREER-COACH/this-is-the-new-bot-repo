"""Test suite for sandwich strategy with real mainnet scenarios"""
import pytest
import time
import json
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from web3 import Web3
from eth_utils import to_checksum_address

from src.sandwich_strategy_v2 import SandwichStrategyV2
from test.mock_loans import MockFlashLoan

# Constants from mainnet
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
UNISWAP_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
UNISWAP_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
SUSHISWAP_ROUTER = "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F"
SUSHISWAP_FACTORY = "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac"

def create_mock_web3():
    """Create mock Web3 instance with realistic mainnet behavior"""
    mock_web3 = Mock()
    mock_web3.eth = Mock()
    
    # Mock realistic gas prices and block data
    mock_web3.eth.get_block = AsyncMock(return_value={
        'baseFeePerGas': Web3.to_wei(30, 'gwei'),  # Typical base fee
        'timestamp': int(time.time()),
        'transactions': [f"0x{'1'*64}" for _ in range(100)],  # Realistic block fullness
        'gasUsed': 12000000,  # ~80% full block
        'gasLimit': 15000000  # Current mainnet gas limit
    })
    
    # Mock EIP-1559 transaction data
    mock_web3.eth.get_transaction = AsyncMock(return_value={
        'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
        'maxFeePerGas': Web3.to_wei(100, 'gwei'),
        'gasPrice': Web3.to_wei(50, 'gwei'),
        'nonce': 100,
        'value': Web3.to_wei(1, 'ether')
    })
    
    mock_web3.to_wei = Web3.to_wei
    mock_web3.from_wei = Web3.from_wei
    
    # Mock contract with realistic responses
    mock_contract = Mock()
    mock_contract.address = UNISWAP_ROUTER
    mock_contract.functions = Mock()
    mock_web3.eth.contract = Mock(return_value=mock_contract)
    
    return mock_web3

def create_mock_dex_handler():
    """Create mock DEX handler with realistic mainnet behavior"""
    mock_handler = Mock()
    
    # Mock WETH/USDC pool data (real mainnet values)
    pool_data = {
        'pair_address': to_checksum_address('0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc'),
        'reserves': {
            'token0': Web3.to_wei(10000, 'ether'),  # 10,000 ETH (~$20M)
            'token1': Web3.to_wei(20000000, 'ether')  # 20M USDC
        },
        'fee': Decimal('0.003'),  # 0.3% fee
        'token0': WETH,
        'token1': USDC,
        'decimals0': 18,
        'decimals1': 6,
        'block_timestamp_last': int(time.time())
    }
    
    # Mock realistic swap data
    swap_data = {
        'dex': 'uniswap',
        'path': [WETH, USDC],
        'amountIn': Web3.to_wei(5, 'ether'),  # 5 ETH (~$10,000)
        'method': 'swapExactTokensForTokens',
        'deadline': int(time.time()) + 120  # 2 min deadline
    }
    
    mock_handler.decode_swap_data = Mock(return_value=swap_data)
    mock_handler.get_pool_info = AsyncMock(return_value=pool_data)
    mock_handler.calculate_price_impact = Mock(return_value=Decimal('0.01'))  # 1% impact
    
    def update_pool_reserves(token0_reserve: int, token1_reserve: int):
        """Update pool reserves with validation"""
        if token0_reserve <= 0 or token1_reserve <= 0:
            raise ValueError("Reserves must be positive")
            
        new_pool_data = pool_data.copy()
        new_pool_data['reserves'] = {
            'token0': Web3.to_wei(token0_reserve, 'ether'),
            'token1': Web3.to_wei(token1_reserve, 'ether')
        }
        mock_handler.get_pool_info.return_value = new_pool_data
        
    mock_handler.update_pool_reserves = update_pool_reserves
    return mock_handler

def create_test_config():
    """Create realistic mainnet configuration"""
    return {
        'strategies': {
            'sandwich': {
                'min_profit_wei': Web3.to_wei(0.05, 'ether'),  # 0.05 ETH min profit
                'max_position_size': Web3.to_wei(50, 'ether'),  # Max 50 ETH position
                'max_price_impact': '0.03',  # Max 3% price impact
                'min_liquidity': Web3.to_wei(100, 'ether'),  # Min 100 ETH liquidity
                'max_gas_price': Web3.to_wei(300, 'gwei'),  # Max 300 gwei
                'slippage_tolerance': '0.005',  # 0.5% slippage
                'competition_factor': '1.2'  # 20% buffer for competition
            }
        },
        'dex': {
            'uniswap_v2_router': UNISWAP_ROUTER,
            'uniswap_v2_factory': UNISWAP_FACTORY,
            'sushiswap_router': SUSHISWAP_ROUTER,
            'sushiswap_factory': SUSHISWAP_FACTORY,
            'uniswap_init_code_hash': "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f",
            'sushiswap_init_code_hash': "0xe18a34eb0e04b04f7a0ac29a6e80748dca96319b42c54d679cb821dca90c6303"
        },
        'flash_loan': {
            'preferred_provider': 'aave',
            'providers': {
                'aave': {
                    'pool_address_provider': '0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5',
                    'fee': '0.0009'  # 0.09% fee
                }
            }
        },
        'contracts': {
            'arbitrage_contract': to_checksum_address('0x1234567890123456789012345678901234567890')
        },
        'gas_limits': {
            'sandwich_frontrun': 300000,
            'sandwich_backrun': 300000
        },
        'monitoring': {
            'max_pending_txs': 100,
            'block_confirmations': 1,
            'gas_price_update_interval': 1,
            'competition_window': 300  # 5 minutes
        }
    }

@pytest.fixture
def strategy():
    """Create sandwich strategy with realistic mainnet mocks"""
    web3 = create_mock_web3()
    config = create_test_config()
    dex_handler = create_mock_dex_handler()
    
    with patch('src.base_strategy.FlashLoan', MockFlashLoan), \
         patch('src.sandwich_strategy_v2.DEXHandler', return_value=dex_handler):
        strategy = SandwichStrategyV2(web3, config)
        strategy.web3 = web3  # Ensure web3 instance is properly set
        strategy.dex_handler = dex_handler
        return strategy

@pytest.mark.asyncio
async def test_analyze_profitable_sandwich(strategy):
    """Test profitable sandwich opportunity with realistic values"""
    # Simulate a 5 ETH swap on Uniswap WETH/USDC pool
    victim_tx = {
        'hash': '0x' + '1' * 64,
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(5, 'ether'),
        'gasPrice': Web3.to_wei(35, 'gwei'),
        'maxFeePerGas': Web3.to_wei(100, 'gwei'),
        'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei')
    }

    result = await strategy.analyze_transaction(victim_tx)

    assert result is not None, "Should identify profitable opportunity"
    assert result['type'] == 'sandwich'
    assert result['token_in'] == WETH
    assert result['token_out'] == USDC
    assert result['frontrun_amount'] > 0
    assert result['backrun_amount'] > 0
    assert result['expected_profit'] > strategy.min_profit_wei
    assert Decimal(str(result['frontrun_amount'])) <= Decimal(str(strategy.max_position_size))

@pytest.mark.asyncio
async def test_analyze_high_price_impact(strategy):
    """Test rejection of high price impact opportunity"""
    # Simulate a 100 ETH swap (too large relative to pool size)
    victim_tx = {
        'hash': '0x' + '1' * 64,
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(100, 'ether'),
        'gasPrice': Web3.to_wei(120, 'gwei')
    }

    # Update pool with limited liquidity (200 ETH, 400K USDC)
    strategy.dex_handler.update_pool_reserves(200, 400000)
    strategy.dex_handler.calculate_price_impact.return_value = Decimal('0.05')  # 5% impact

    result = await strategy.analyze_transaction(victim_tx)
    assert result is None, "Should reject high price impact opportunity"

@pytest.mark.asyncio
async def test_analyze_high_gas_price(strategy):
    """Test rejection of high gas price opportunity"""
    victim_tx = {
        'hash': '0x' + '1' * 64,
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(5, 'ether'),
        'gasPrice': Web3.to_wei(500, 'gwei')  # Very high gas price
    }

    result = await strategy.analyze_transaction(victim_tx)
    assert result is None, "Should reject high gas price opportunity"

@pytest.mark.asyncio
async def test_analyze_low_liquidity(strategy):
    """Test rejection of low liquidity opportunity"""
    victim_tx = {
        'hash': '0x' + '1' * 64,
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(1, 'ether'),
        'gasPrice': Web3.to_wei(35, 'gwei')
    }

    # Update pool with very low liquidity
    strategy.dex_handler.update_pool_reserves(50, 100000)  # 50 ETH, 100K USDC
    
    result = await strategy.analyze_transaction(victim_tx)
    assert result is None, "Should reject low liquidity opportunity"

@pytest.mark.asyncio
async def test_analyze_competition_monitoring(strategy):
    """Test competition monitoring and adjustment"""
    # Simulate successful sandwiches
    strategy._recent_sandwiches = [
        {'timestamp': time.time() - 60, 'success': True},
        {'timestamp': time.time() - 120, 'success': True},
        {'timestamp': time.time() - 180, 'success': True}
    ]
    
    victim_tx = {
        'hash': '0x' + '1' * 64,
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(5, 'ether'),
        'gasPrice': Web3.to_wei(35, 'gwei')
    }

    result = await strategy.analyze_transaction(victim_tx)
    assert result is not None
    assert result['competition_level'] <= 1.0, "Competition level should decrease with high success rate"

    # Simulate failed sandwiches
    strategy._recent_sandwiches = [
        {'timestamp': time.time() - 60, 'success': False},
        {'timestamp': time.time() - 120, 'success': False},
        {'timestamp': time.time() - 180, 'success': False}
    ]

    result = await strategy.analyze_transaction(victim_tx)
    assert result is not None
    assert result['competition_level'] > 1.0, "Competition level should increase with low success rate"

@pytest.mark.asyncio
async def test_analyze_cross_dex_opportunity(strategy):
    """Test analysis of cross-DEX opportunities"""
    # Simulate a swap on Sushiswap
    victim_tx = {
        'hash': '0x' + '1' * 64,
        'to': SUSHISWAP_ROUTER,
        'value': Web3.to_wei(5, 'ether'),
        'gasPrice': Web3.to_wei(35, 'gwei')
    }

    # Update mock to return Sushiswap data
    strategy.dex_handler.decode_swap_data.return_value['dex'] = 'sushiswap'

    result = await strategy.analyze_transaction(victim_tx)
    assert result is not None
    assert result['dex'] == 'sushiswap'

@pytest.mark.asyncio
async def test_analyze_token_pair_validation(strategy):
    """Test validation of different token pairs"""
    # Test WETH/USDT pair
    victim_tx = {
        'hash': '0x' + '1' * 64,
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(5, 'ether'),
        'gasPrice': Web3.to_wei(35, 'gwei')
    }

    # Update mock for WETH/USDT pair
    strategy.dex_handler.decode_swap_data.return_value['path'] = [WETH, USDT]
    strategy.dex_handler.get_pool_info.return_value['token1'] = USDT
    strategy.dex_handler.get_pool_info.return_value['decimals1'] = 6

    result = await strategy.analyze_transaction(victim_tx)
    assert result is not None
    assert result['token_out'] == USDT

@pytest.mark.asyncio
async def test_analyze_slippage_protection(strategy):
    """Test slippage protection mechanisms"""
    victim_tx = {
        'hash': '0x' + '1' * 64,
        'to': UNISWAP_ROUTER,
        'value': Web3.to_wei(5, 'ether'),
        'gasPrice': Web3.to_wei(35, 'gwei')
    }

    # Simulate high volatility conditions
    strategy.dex_handler.calculate_price_impact.return_value = Decimal('0.02')  # 2% impact
    result = await strategy.analyze_transaction(victim_tx)
    
    assert result is not None
    # Verify frontrun amount is adjusted for slippage
    assert result['frontrun_amount'] <= Web3.to_wei(7.5, 'ether'), "Frontrun amount should be limited in volatile conditions"
