"""Mock classes for testing sandwich strategy"""
from unittest.mock import Mock, AsyncMock
from web3 import Web3
from eth_utils import to_checksum_address
from decimal import Decimal
import time

# Constants
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
POOL = "0x1234567890123456789012345678901234567890"

class MockDexHandler:
    """Mock DEX handler for testing"""
    
    def __init__(self):
        self.decode_swap_data = Mock()
        self.get_pool_info = AsyncMock()
        self.calculate_price_impact = Mock(return_value=Decimal('0.01'))
        
        # Set default responses
        self._setup_default_responses()
        
    def _setup_default_responses(self):
        """Setup default mock responses"""
        self.decode_swap_data.return_value = {
            'dex': 'uniswap',
            'path': [WETH, DAI],
            'amountIn': Web3.to_wei(5, 'ether'),
            'method': 'swapExactTokensForTokens'
        }
        
        self.get_pool_info.return_value = {
            'pair_address': POOL,
            'reserves': {
                'token0': Web3.to_wei(10000, 'ether'),
                'token1': Web3.to_wei(20000000, 'ether')
            },
            'fee': Decimal('0.003'),
            'token0': WETH,
            'token1': DAI,
            'decimals0': 18,
            'decimals1': 18,
            'block_timestamp_last': int(time.time()) - 1
        }
        
    def update_pool_reserves(self, token0_reserve: int, token1_reserve: int):
        """Update pool reserves"""
        pool_info = self.get_pool_info.return_value
        pool_info['reserves']['token0'] = Web3.to_wei(token0_reserve, 'ether')
        pool_info['reserves']['token1'] = Web3.to_wei(token1_reserve, 'ether')
        self.get_pool_info.return_value = pool_info

class MockWeb3:
    """Mock Web3 instance"""
    
    def __init__(self):
        self.eth = Mock()
        self.eth.chain_id = 1
        self.eth.gas_price = Web3.to_wei(30, 'gwei')
        
        # Mock async methods
        self.eth.get_block = AsyncMock(return_value={
            'baseFeePerGas': Web3.to_wei(30, 'gwei'),
            'timestamp': int(time.time()),
            'transactions': [f"0x{'1'*64}" for _ in range(100)],
            'gasUsed': 12000000,
            'gasLimit': 15000000
        })
        
        self.eth.get_transaction = AsyncMock(return_value={
            'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
            'maxFeePerGas': Web3.to_wei(100, 'gwei'),
            'gasPrice': Web3.to_wei(50, 'gwei')
        })
        
        # Mock contract
        mock_contract = Mock()
        mock_contract.address = POOL
        mock_contract.functions = Mock()
        mock_contract.functions.factory = Mock(return_value=Mock(
            call=Mock(return_value=to_checksum_address("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"))
        ))
        
        self.eth.contract = Mock(return_value=mock_contract)
        
        # Helper methods
        self.to_wei = Web3.to_wei
        self.from_wei = Web3.from_wei

class MockFlashLoan:
    """Mock flash loan for testing"""
    
    def __init__(self, w3, config):
        self.w3 = w3
        self.config = config
        self.preferred_provider = config['flash_loan']['preferred_provider']
        self.providers = {
            'aave': Mock(fee=Decimal('0.0009'))
        }
        
    async def simulate_flash_loan(self, token, amount, callback_data):
        """Simulate flash loan"""
        return {
            'success': True,
            'gas_used': 500000,
            'return_data': b'0x' + b'0' * 64
        }
        
    async def execute_flash_loan(self, token, amount, callback_data):
        """Execute flash loan"""
        return True
