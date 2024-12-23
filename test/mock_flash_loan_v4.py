"""Mock flash loan provider for testing"""
from unittest.mock import Mock, AsyncMock
from decimal import Decimal
from typing import Dict, Any, Tuple

class MockFlashLoan:
    """Mock flash loan provider"""
    
    def __init__(self, web3, config):
        """Initialize mock flash loan"""
        self.web3 = web3
        self.config = config
        self.preferred_provider = 'aave'
        self.providers = {
            'aave': Mock(fee=Decimal('0.0009'))
        }
        
        # Mock methods
        self.simulate_flash_loan = AsyncMock(return_value={
            'success': True,
            'return_data': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x64',  # Represents 100 wei profit
            'gas_used': 200000
        })
        self.execute_flash_loan = AsyncMock(return_value=True)
        
    async def get_loan(self, token: str, amount: int) -> bool:
        """Mock getting a flash loan"""
        return True
        
    async def repay_loan(self, token: str, amount: int) -> bool:
        """Mock repaying a flash loan"""
        return True
        
    async def calculate_fees(self, token: str, amount: int) -> Decimal:
        """Mock calculating flash loan fees"""
        return Decimal('0.001') * Decimal(str(amount))  # 0.1% fee
