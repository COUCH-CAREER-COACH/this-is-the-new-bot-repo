"""Mock classes for testing MEV strategies"""
from unittest.mock import Mock, AsyncMock
from web3 import Web3
from eth_utils import to_checksum_address
from decimal import Decimal
import time

class MockContract:
    """Mock contract that returns valid Ethereum addresses and handles common contract calls"""
    
    def __init__(self, address: str, abi: list = None):
        self.address = to_checksum_address(address)
        self.functions = Mock()
        
        # Mock common view functions
        self.functions.factory = Mock(return_value=Mock(
            call=Mock(return_value=to_checksum_address("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"))
        ))
        
        # Mock pool functions
        self.functions.getReserves = Mock(return_value=Mock(
            call=Mock(return_value=[
                Web3.to_wei(10000, 'ether'),  # token0 reserves (10,000 ETH)
                Web3.to_wei(20000000, 'ether'),  # token1 reserves (20M DAI)
                int(time.time())  # Last update timestamp
            ])
        ))
        
        # Mock token functions
        self.functions.token0 = Mock(return_value=Mock(
            call=Mock(return_value=to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"))
        ))
        self.functions.token1 = Mock(return_value=Mock(
            call=Mock(return_value=to_checksum_address("0x6B175474E89094C44Da98b954EedeAC495271d0F"))
        ))
        
        # Mock factory functions
        self.functions.allPairsLength = Mock(return_value=Mock(
            call=Mock(return_value=1000)
        ))
        self.functions.getPair = Mock(return_value=Mock(
            call=Mock(return_value=to_checksum_address("0x1234567890123456789012345678901234567890"))
        ))
        
        # Mock router functions
        self.functions.getAmountsOut = Mock(return_value=Mock(
            call=Mock(return_value=[
                Web3.to_wei(1, 'ether'),
                Web3.to_wei(2000, 'ether')
            ])
        ))
        
        # Mock flash loan functions
        self.functions.flashLoan = Mock()
        self.functions.FLASHLOAN_PREMIUM_TOTAL = Mock(return_value=Mock(
            call=Mock(return_value=9)  # 0.09% fee
        ))

    def encodeABI(self, fn_name: str = None, args: list = None):
        """Mock ABI encoding"""
        return b'0x' + b'0' * 64

class MockWeb3:
    """Mock Web3 instance with realistic chain behavior"""
    
    def __init__(self):
        self.eth = Mock()
        self.eth.chain_id = 1
        self.eth.gas_price = Web3.to_wei(30, 'gwei')
        
        # Mock block data
        self.eth.get_block = Mock(return_value={
            'baseFeePerGas': Web3.to_wei(30, 'gwei'),
            'timestamp': int(time.time()),
            'transactions': [f"0x{'1'*64}" for _ in range(100)],
            'gasUsed': 12000000,
            'gasLimit': 15000000
        })
        
        # Mock transaction data
        self.eth.get_transaction = Mock(return_value={
            'maxPriorityFeePerGas': Web3.to_wei(2, 'gwei'),
            'maxFeePerGas': Web3.to_wei(100, 'gwei'),
            'gasPrice': Web3.to_wei(50, 'gwei')
        })
        
        self.eth.get_transaction_count = Mock(return_value=100)
        self.eth.contract = Mock(side_effect=self._get_mock_contract)
        self.eth.account = Mock()
        
        # Helper methods from Web3
        self.to_wei = Web3.to_wei
        self.from_wei = Web3.from_wei
        
    def _get_mock_contract(self, address=None, abi=None):
        """Return a mock contract with valid Ethereum address"""
        if not address:
            address = "0x1234567890123456789012345678901234567890"
        return MockContract(address, abi)

class MockDexHandler:
    """Mock DEX handler for testing sandwich strategies"""
    
    def __init__(self):
        self.decode_swap_data = Mock()
        self.get_pool_info = Mock()
        self.calculate_price_impact = Mock(return_value=Decimal('0.01'))  # 1% impact
        
        # Setup initial mock data
        self._setup_mock_data()
        
    def _setup_mock_data(self):
        """Setup initial mock data with realistic values"""
        pool_data = {
            'pair_address': to_checksum_address('0x1234567890123456789012345678901234567890'),
            'reserves': {
                'token0': Web3.to_wei(10000, 'ether'),  # 10,000 ETH
                'token1': Web3.to_wei(20000000, 'ether')  # 20M DAI
            },
            'fee': Decimal('0.003'),  # 0.3% fee
            'token0': to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),  # WETH
            'token1': to_checksum_address("0x6B175474E89094C44Da98b954EedeAC495271d0F"),  # DAI
            'decimals0': 18,
            'decimals1': 18,
            'block_timestamp_last': int(time.time()) - 1
        }
        
        swap_data = {
            'dex': 'uniswap',
            'path': [
                to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),  # WETH
                to_checksum_address("0x6B175474E89094C44Da98b954EedeAC495271d0F")   # DAI
            ],
            'amountIn': Web3.to_wei(5, 'ether'),  # 5 ETH
            'method': 'swapExactTokensForTokens'
        }
        
        self.get_pool_info.return_value = pool_data
        self.decode_swap_data.return_value = swap_data
        
    def update_pool_reserves(self, token0_reserve: int, token1_reserve: int):
        """Update pool reserves for testing different scenarios"""
        pool_data = self.get_pool_info.return_value
        pool_data['reserves']['token0'] = Web3.to_wei(token0_reserve, 'ether')
        pool_data['reserves']['token1'] = Web3.to_wei(token1_reserve, 'ether')
        self.get_pool_info.return_value = pool_data
