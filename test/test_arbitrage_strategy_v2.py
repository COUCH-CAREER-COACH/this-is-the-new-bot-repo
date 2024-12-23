"""Tests for Enhanced Arbitrage Strategy"""
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from decimal import Decimal
from web3 import Web3
import asyncio
import time
import pytest

from src.arbitrage_strategy import EnhancedArbitrageStrategy
from src.utils.dex_utils import DEXHandler

class TestEnhancedArbitrageStrategy(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create Web3 mock with eth module
        self.w3 = Mock(spec=Web3)
        self.w3.eth = Mock()
        self.w3.eth.contract = Mock()
        self.w3.eth.get_transaction_count = AsyncMock(return_value=0)
        self.w3.eth.gas_price = 50000000000  # 50 GWEI
        self.w3.eth.block_number = 1000000
        self.w3.eth.get_block = AsyncMock(return_value={'timestamp': int(time.time())})

        # Mock contract interactions
        mock_contract = Mock()
        mock_contract.functions = Mock()

        # Mock Aave pool provider with synchronous call
        mock_pool_fn = Mock()
        mock_pool_fn.call = Mock(return_value="0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9")
        mock_contract.functions.getPool = Mock(return_value=mock_pool_fn)

        # Mock pool contract functions
        mock_max_loan_fn = Mock()
        mock_max_loan_fn.call = Mock(return_value=1000000000000000000000)  # 1000 ETH
        mock_contract.functions.getMaxFlashLoan = Mock(return_value=mock_max_loan_fn)

        # Mock flash loan functions
        mock_flash_loan_fn = Mock()
        mock_flash_loan_fn.call = Mock(return_value=True)
        mock_flash_loan_fn.build_transaction = Mock(
            return_value={
                'to': '0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9',
                'data': '0x',
                'value': 0,
                'gas': 500000,
                'maxFeePerGas': 50000000000,
                'maxPriorityFeePerGas': 2000000000
            }
        )
        mock_contract.functions.flashLoan = Mock(return_value=mock_flash_loan_fn)

        # Mock pair contract functions
        mock_reserves_fn = Mock()
        mock_reserves_fn.call = Mock(return_value=[
            100000000000000000000,  # 100 ETH
            200000000000000000000,  # 200 tokens
            int(time.time())
        ])
        mock_contract.functions.getReserves = Mock(return_value=mock_reserves_fn)

        # Mock factory contract functions
        mock_pair_fn = Mock()
        mock_pair_fn.call = Mock(return_value="0x1234567890123456789012345678901234567890")
        mock_contract.functions.getPair = Mock(return_value=mock_pair_fn)

        # Mock transaction signing and sending
        self.w3.eth.account = Mock()
        self.w3.eth.account.sign_transaction = Mock(
            return_value=Mock(rawTransaction=b'0x')
        )
        self.w3.eth.send_raw_transaction = AsyncMock(
            return_value='0x1234'
        )
        self.w3.eth.wait_for_transaction_receipt = AsyncMock(
            return_value={'status': 1}
        )

        # Mock contract creation
        mock_contract.address = "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"
        self.w3.eth.contract.return_value = mock_contract

        # Mock Web3 utils
        self.w3.to_wei = Web3.to_wei
        self.w3.from_wei = Web3.from_wei
        self.w3.is_address = Web3.is_address
        self.w3.keccak = Web3.keccak

        self.config = {
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
                'sushiswap_router': '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',
                'sushiswap_factory': '0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac'
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

        # Initialize strategy
        self.strategy = EnhancedArbitrageStrategy(self.w3, self.config)
