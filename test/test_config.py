"""Base test configuration and fixtures"""
from decimal import Decimal
from web3 import Web3
import time
from unittest.mock import Mock, AsyncMock

def get_test_config():
    """Get base test configuration."""
    return {
        'strategies': {
            'arbitrage': {
                'min_profit_wei': '100000000000000000',
                'max_position_size': '50000000000000000000',
                'max_price_impact': '0.05'
            }
        },
        'dex': {
            'uniswap_v2_router': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
            'uniswap_v2_factory': '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f',
            'uniswap_init_code_hash': '0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f',
            'sushiswap_router': '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',
            'sushiswap_factory': '0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac',
            'sushiswap_init_code_hash': '0xe18a34eb0e04b04f7a0ac29a6e80748dca96319b42c54d679cb821dca90c6303',
            'uniswap_fee': '0.003',
            'sushiswap_fee': '0.003'
        },
        'flash_loan': {
            'providers': {
                'aave': {
                    'pool_address_provider': '0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e',
                    'fee': '0.0009'
                }
            },
            'preferred_provider': 'aave'
        }
    }

def get_mock_web3():
    """Get mocked Web3 instance."""
    w3 = Mock(spec=Web3)
    w3.eth = Mock()
    w3.eth.contract = Mock()
    w3.eth.get_transaction_count = AsyncMock(return_value=0)
    w3.eth.gas_price = 50000000000  # 50 GWEI
    w3.eth.block_number = 1000000
    w3.eth.get_block = AsyncMock(return_value={'timestamp': int(time.time())})
    w3.eth.chain_id = 1  # Mainnet
    w3.eth.get_code = Mock(return_value=b'some_code')
    w3.eth.max_priority_fee_per_gas = 2000000000  # 2 GWEI

    # Mock Web3 utils
    w3.to_wei = Web3.to_wei
    w3.from_wei = Web3.from_wei
    w3.is_address = Web3.is_address
    w3.keccak = Web3.keccak
    w3.to_checksum_address = Web3.to_checksum_address

    return w3

def get_mock_contract():
    """Get mocked contract instance."""
    mock_contract = Mock()
    mock_contract.functions = Mock()
    mock_contract.functions.getPool = Mock(return_value=Mock(
        call=Mock(return_value="0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9")
    ))
    mock_contract.functions.getMaxFlashLoan = Mock(return_value=Mock(
        call=Mock(return_value=1000000000000000000000)
    ))
    mock_contract.address = "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"
    return mock_contract

def get_mock_pool_info(timestamp=None):
    """Get mocked pool info."""
    if timestamp is None:
        timestamp = int(time.time())
    
    return {
        'pair_address': '0x1234567890123456789012345678901234567890',
        'reserves': {
            'token0': 100000000000000000000,  # 100 ETH
            'token1': 200000000000000000000   # 200 DAI
        },
        'fee': Decimal('0.003'),
        'block_timestamp_last': timestamp
    }

def get_mock_swap_data():
    """Get mocked swap data."""
    return {
        'dex': 'uniswap',
        'path': [
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
            '0x6B175474E89094C44Da98b954EedeAC495271d0F'   # DAI
        ],
        'amountIn': 1000000000000000000  # 1 ETH
    }

def get_mock_transaction():
    """Get mocked transaction data."""
    return {
        'hash': '0x123',
        'input': '0x38ed1739',  # swapExactTokensForTokens
        'to': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'.lower(),  # Uniswap router
        'value': 1000000000000000000  # 1 ETH
    }
