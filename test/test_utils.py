"""Test utilities for mocking Web3 functionality"""
from typing import Dict, Any
from web3 import Web3
from eth_utils import to_checksum_address
from decimal import Decimal

class MockContract:
    """Mock contract for testing"""
    def __init__(self, address: str):
        self.address = to_checksum_address(address)
        self.functions = Mock()

def create_mock_web3():
    """Create a mock Web3 instance with necessary functionality"""
    mock_web3 = Mock()
    mock_web3.eth = Mock()
    mock_web3.eth.chain_id = 1
    mock_web3.eth.gas_price = Web3.to_wei(30, 'gwei')
    
    # Mock block data
    mock_web3.eth.get_block = AsyncMock(return_value={
        'baseFeePerGas': Web3.to_wei(30, 'gwei'),
        'timestamp': int(time.time()),
        'transactions': [f"0x{'1'*64}" for _ in range(100)],
        'gasUsed': 12000000,
        'gasLimit': 15000000
    })
    
    # Mock transaction data
    mock_web3.eth.get_transaction = AsyncMock(return_value={
        'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
        'maxFeePerGas': Web3.to_wei(100, 'gwei'),
        'gasPrice': Web3.to_wei(50, 'gwei')
    })
    
    # Mock contract creation
    def create_contract(address, abi):
        contract = MockContract(address)
        contract.functions.factory = Mock(return_value=Mock(
            call=Mock(return_value=to_checksum_address("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"))
        ))
        contract.functions.getReserves = Mock(return_value=Mock(
            call=Mock(return_value=[
                Web3.to_wei(10000, 'ether'),
                Web3.to_wei(20000000, 'ether'),
                int(time.time())
            ])
        ))
        return contract
        
    mock_web3.eth.contract = Mock(side_effect=create_contract)
    
    # Helper methods
    mock_web3.to_wei = Web3.to_wei
    mock_web3.from_wei = Web3.from_wei
    
    return mock_web3

def create_mock_dex_handler():
    """Create a mock DEX handler with realistic behavior"""
    mock_handler = Mock()
    
    # Mock pool data
    pool_data = {
        'pair_address': to_checksum_address('0x1234567890123456789012345678901234567890'),
        'reserves': {
            'token0': Web3.to_wei(10000, 'ether'),
            'token1': Web3.to_wei(20000000, 'ether')
        },
        'fee': Decimal('0.003'),
        'token0': to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
        'token1': to_checksum_address("0x6B175474E89094C44Da98b954EedeAC495271d0F"),
        'decimals0': 18,
        'decimals1': 18,
        'block_timestamp_last': int(time.time())
    }
    
    # Mock swap data
    swap_data = {
        'dex': 'uniswap',
        'path': [
            to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
            to_checksum_address("0x6B175474E89094C44Da98b954EedeAC495271d0F")
        ],
        'amountIn': Web3.to_wei(5, 'ether'),
        'method': 'swapExactTokensForTokens'
    }
    
    # Setup mock methods
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

def create_test_config():
    """Create a test configuration with realistic values"""
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
            'uniswap_v2_router': to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
            'uniswap_v2_factory': to_checksum_address("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"),
            'uniswap_init_code_hash': "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f"
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
