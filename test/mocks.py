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
        self.functions.getReserves = AsyncMock(return_value=[
            Web3.to_wei(10000, 'ether'),  # token0 reserves (10,000 ETH)
            Web3.to_wei(20000000, 'ether'),  # token1 reserves (20M DAI)
            int(time.time())  # Last update timestamp
        ])
        
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
            call=AsyncMock(return_value=to_checksum_address("0x1234567890123456789012345678901234567890"))
        ))
        
        # Mock router functions
        self.functions.getAmountsOut = AsyncMock(return_value=[
            Web3.to_wei(1, 'ether'),
            Web3.to_wei(2000, 'ether')
        ])
        
        # Mock flash loan functions
        self.functions.flashLoan = Mock()
        self.functions.FLASHLOAN_PREMIUM_TOTAL = Mock(return_value=Mock(
            call=Mock(return_value=9)  # 0.09% fee
        ))

    def encodeABI(self, fn_name: str = None, args: list = None):
        """Mock ABI encoding"""
        return b'0x' + b'0' * 64
