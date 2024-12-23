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
        self.execute = AsyncMock(side_effect=self._mock_execute)
        self.simulate_flash_loan = AsyncMock(return_value=(True, Decimal('0.1')))  # Mock successful simulation
        
    async def get_loan(self, token: str, amount: int) -> bool:
        """Mock getting a flash loan"""
        return True
        
    async def repay_loan(self, token: str, amount: int) -> bool:
        """Mock repaying a flash loan"""
        return True
        
    async def calculate_fees(self, token: str, amount: int) -> Decimal:
        """Mock calculating flash loan fees"""
        return Decimal('0.001') * Decimal(str(amount))  # 0.1% fee
        
    async def _mock_execute(self, token: str, amount: int, callback_data: bytes, tx_params: Dict[str, Any] = None) -> Tuple[bool, int]:
        """Mock flash loan execution with proper return type"""
        # Return (success, profit)
        return True, int(Decimal('0.1') * Decimal(str(amount)))
