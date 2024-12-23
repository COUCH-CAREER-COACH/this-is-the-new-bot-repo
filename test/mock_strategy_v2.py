"""Mock strategy for testing"""
from unittest.mock import Mock, AsyncMock
from decimal import Decimal
from web3 import Web3
from eth_utils import to_checksum_address

class MockStrategy:
    """Mock strategy for testing"""
    
    def __init__(self, web3, config):
        """Initialize mock strategy"""
        self.web3 = web3
        self.config = config
        
        # Mock transaction analysis
        self.analyze_transaction = AsyncMock(return_value={
            'type': 'sandwich',
            'dex': 'uniswap',
            'token_in': config['dex']['uniswap_v2_router'],
            'token_out': config['dex']['uniswap_v2_factory'],
            'victim_amount': Web3.to_wei(5, 'ether'),
            'frontrun_amount': Web3.to_wei(2, 'ether'),
            'backrun_amount': Web3.to_wei(1.9, 'ether'),
            'pool_address': to_checksum_address('0x1234567890123456789012345678901234567890'),
            'gas_price': Web3.to_wei(50, 'gwei'),
            'expected_profit': Web3.to_wei(0.1, 'ether')
        })
        
        # Mock execution
        self.execute_opportunity = AsyncMock(return_value=True)
        
        # Mock pool info
        self.get_pool_info = AsyncMock(return_value={
            'pair_address': to_checksum_address('0x1234567890123456789012345678901234567890'),
            'reserves': {
                'token0': Web3.to_wei(10000, 'ether'),
                'token1': Web3.to_wei(20000000, 'ether')
            },
            'fee': Decimal('0.003'),
            'token0': config['dex']['uniswap_v2_router'],
            'token1': config['dex']['uniswap_v2_factory'],
            'decimals0': 18,
            'decimals1': 18
        })
        
        # Mock price impact calculation
        self.calculate_price_impact = Mock(return_value=Decimal('0.02'))
        
        # Mock profit calculation
        self.calculate_profit = Mock(return_value=Web3.to_wei(0.1, 'ether'))
        
        # Mock gas estimation
        self.estimate_gas = AsyncMock(return_value=200000)
        
        # Mock transaction building
        self.build_transaction = AsyncMock(return_value={
            'gas': 200000,
            'maxFeePerGas': Web3.to_wei(100, 'gwei'),
            'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
            'nonce': 1
        })
