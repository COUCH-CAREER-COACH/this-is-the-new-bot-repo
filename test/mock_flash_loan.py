"""Mock flash loan provider for testing"""
from unittest.mock import Mock, AsyncMock

class MockFlashLoan:
    """Mock flash loan provider"""
    
    def __init__(self, web3, config):
        """Initialize mock flash loan"""
        self.web3 = web3
        self.config = config
        self.execute = AsyncMock(return_value=(True, 0))  # Mock successful execution
        
    async def get_loan(self, token, amount):
        """Mock getting a flash loan"""
        return True
        
    async def repay_loan(self, token, amount):
        """Mock repaying a flash loan"""
        return True
