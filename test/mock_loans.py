"""Mock flash loan implementations for testing."""
from typing import Dict
from web3 import Web3
from decimal import Decimal
from unittest.mock import Mock, AsyncMock

class MockFlashLoanProvider:
    """Mock flash loan provider that simulates Aave behavior."""
    
    def __init__(self, w3: Web3, config: Dict):
        self.w3 = w3
        self.config = config
        self.fee = Decimal(str(config.get('fee', '0.0009')))  # Default to 0.09%
        
        # Mock pool address - use a valid Ethereum address format
        self.pool_address = "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"
        
        # Mock contract that returns valid addresses
        self.pool_contract = self._get_mock_pool_contract()

    def _get_mock_pool_contract(self):
        """Get a mock pool contract that returns valid data."""
        mock_contract = Mock()
        mock_contract.address = self.pool_address
        
        # Mock the getMaxFlashLoan function
        mock_contract.functions = Mock()
        mock_contract.functions.getMaxFlashLoan = Mock(return_value=Mock(
            call=Mock(return_value=Web3.to_wei(1000, 'ether'))  # 1000 ETH
        ))
        
        # Mock the flashLoan function
        mock_contract.functions.flashLoan = Mock(return_value=Mock(
            call=Mock(return_value=True)
        ))
        
        return mock_contract

    async def get_max_flash_loan(self, token: str) -> int:
        """Get mock maximum flash loan amount."""
        return Web3.to_wei(1000, 'ether')  # Always return 1000 ETH for testing

    async def execute_flash_loan(self, token: str, amount: int, callback_data: bytes) -> bool:
        """Execute mock flash loan."""
        return True  # Always succeed in test environment

class MockFlashLoan:
    """Mock flash loan manager for testing."""
    
    def __init__(self, w3: Web3, config: Dict):
        self.w3 = w3
        self.config = config
        self.providers = {}
        
        # Initialize only configured providers
        flash_loan_config = config.get('flash_loan', {})
        providers_config = flash_loan_config.get('providers', {})
        
        # Always initialize Aave provider for testing
        self.providers['aave'] = MockFlashLoanProvider(w3, providers_config.get('aave', {'fee': '0.0009'}))
        self.preferred_provider = flash_loan_config.get('preferred_provider', 'aave')

    async def get_best_flash_loan(self, token: str, amount: int):
        """Get mock best flash loan provider."""
        return self.preferred_provider, self.providers[self.preferred_provider]

    async def execute_flash_loan(self, token: str, amount: int, callback_data: bytes, provider: str = None) -> bool:
        """Execute mock flash loan."""
        return True

    async def simulate_flash_loan(self, token: str, amount: int, callback_data: bytes, provider: str = None) -> Dict:
        """Simulate mock flash loan."""
        return {
            'success': True,
            'gas_used': 500000,
            'return_data': b'0x' + b'0' * 64  # Mock return data for profit calculation
        }
