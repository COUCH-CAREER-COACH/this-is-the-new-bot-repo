"""Tests for Enhanced Arbitrage Strategy"""
import unittest
from unittest.mock import Mock, patch, AsyncMock
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
        
        # Mock Aave pool provider with proper async handling
        mock_pool_call = Mock()
        mock_pool_call.call = AsyncMock(return_value="0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9")
        mock_contract.functions.getPool = Mock(return_value=mock_pool_call)
        
        # Mock pool contract functions
        mock_max_loan_call = Mock()
        mock_max_loan_call.call = AsyncMock(return_value=1000000000000000000000)  # 1000 ETH
        mock_contract.functions.getMaxFlashLoan = Mock(return_value=mock_max_loan_call)
        
        # Mock flash loan functions
        mock_flash_loan_call = Mock()
        mock_flash_loan_call.call = AsyncMock(return_value=True)
        mock_flash_loan_call.build_transaction = Mock(
            return_value={
                'to': '0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9',
                'data': '0x',
                'value': 0,
                'gas': 500000,
                'maxFeePerGas': 50000000000,
                'maxPriorityFeePerGas': 2000000000
            }
        )
        mock_contract.functions.flashLoan = Mock(return_value=mock_flash_loan_call)
        
        # Mock pair contract functions
        mock_reserves_call = Mock()
        mock_reserves_call.call = AsyncMock(return_value=[
            100000000000000000000,  # 100 ETH
            200000000000000000000,  # 200 tokens
            int(time.time())
        ])
        mock_contract.functions.getReserves = Mock(return_value=mock_reserves_call)
        
        # Mock factory contract functions
        mock_pair_call = Mock()
        mock_pair_call.call = AsyncMock(return_value="0x1234567890123456789012345678901234567890")
        mock_contract.functions.getPair = Mock(return_value=mock_pair_call)
        
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

    async def test_analyze_transaction_profitable(self):
        """Test analyzing a profitable arbitrage opportunity."""
        # Mock transaction data
        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',  # swapExactTokensForTokens
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000  # 1 ETH
        }

        # Mock DEX handler methods
        self.strategy.dex_handler.decode_swap_data = AsyncMock(return_value={
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'   # DAI
            ],
            'amountIn': 1000000000000000000  # 1 ETH
        })

        self.strategy.dex_handler.get_pool_info = AsyncMock(side_effect=[
            {  # Uniswap pool
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 200000000000000000000   # 200 DAI
                },
                'fee': Decimal('0.003')
            },
            {  # Sushiswap pool
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 220000000000000000000   # 220 DAI (10% higher price)
                },
                'fee': Decimal('0.003')
            }
        ])

        # Test analysis
        result = await self.strategy.analyze_transaction(tx)

        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'arbitrage')
        self.assertGreater(result['profit'], int(self.config['strategies']['arbitrage']['min_profit_wei']))

    async def test_execute_opportunity_success(self):
        """Test successful execution of arbitrage opportunity."""
        opportunity = {
            'type': 'arbitrage',
            'token_in': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
            'token_out': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
            'amount': 1000000000000000000,
            'profit': 100000000000000000,
            'gas_price': 50000000000,
            'pools': {
                'uniswap': '0x1234567890123456789012345678901234567890',
                'sushiswap': '0x1234567890123456789012345678901234567890'
            }
        }

        # Mock flash loan execution
        self.strategy._execute_with_flash_loan = AsyncMock(return_value=(True, Decimal('0.1')))

        # Test execution
        result = await self.strategy.execute_opportunity(opportunity)

        # Verify result
        self.assertTrue(result)

    async def test_execute_opportunity_failure(self):
        """Test failed execution of arbitrage opportunity."""
        opportunity = {
            'type': 'arbitrage',
            'token_in': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
            'token_out': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
            'amount': 1000000000000000000,
            'profit': 100000000000000000,
            'gas_price': 50000000000,
            'pools': {
                'uniswap': '0x1234567890123456789012345678901234567890',
                'sushiswap': '0x1234567890123456789012345678901234567890'
            }
        }

        # Mock flash loan execution failure
        self.strategy._execute_with_flash_loan = AsyncMock(return_value=(False, Decimal('0')))

        # Test execution
        result = await self.strategy.execute_opportunity(opportunity)

        # Verify result
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
