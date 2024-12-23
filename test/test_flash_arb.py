"""Test flash loan arbitrage strategy"""
import unittest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from web3 import Web3
import time

from src.arbitrage_strategy import EnhancedArbitrageStrategy

class TestFlashArb(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.w3 = Mock(spec=Web3)
        self.w3.eth = Mock()
        self.w3.eth.contract = Mock()
        self.w3.eth.get_transaction_count = AsyncMock(return_value=0)
        self.w3.eth.gas_price = 50000000000  # 50 GWEI
        self.w3.eth.block_number = 1000000
        self.w3.eth.get_block = AsyncMock(return_value={'timestamp': int(time.time())})

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

    @patch('src.base_strategy.MEVStrategy._encode_strategy_callback')
    @patch('src.base_strategy.MEVStrategy._execute_with_flash_loan')
    async def test_flash_loan_arbitrage(self, mock_execute_flash_loan, mock_encode_callback):
        """Test arbitrage execution with flash loan."""
        # Mock contract calls
        mock_contract = Mock()
        mock_contract.functions = Mock()
        mock_contract.functions.getPool = Mock(return_value=Mock(call=Mock(return_value="0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9")))
        mock_contract.functions.getMaxFlashLoan = Mock(return_value=Mock(call=Mock(return_value=1000000000000000000000)))
        mock_contract.functions.flashLoan = Mock(return_value=Mock(
            call=Mock(return_value=True),
            build_transaction=Mock(return_value={
                'to': '0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9',
                'data': '0x',
                'value': 0,
                'gas': 500000,
                'maxFeePerGas': 50000000000,
                'maxPriorityFeePerGas': 2000000000
            })
        ))
        mock_contract.address = "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"
        mock_contract.encodeABI = Mock(return_value=b'0x123456')
        self.w3.eth.contract.return_value = mock_contract

        # Initialize strategy
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock strategy callbacks
        mock_encode_callback.return_value = b'0x123456'
        mock_execute_flash_loan.return_value = (True, Decimal('0.1'))

        # Create test opportunity
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

        # Test execution
        result = await strategy.execute_opportunity(opportunity)

        # Verify result
        self.assertTrue(result)
        mock_encode_callback.assert_called_once()
        mock_execute_flash_loan.assert_called_once()
        
        # Verify flash loan parameters
        flash_loan_args = mock_execute_flash_loan.call_args[0]
        self.assertEqual(flash_loan_args[0], opportunity['token_in'])  # token
        self.assertEqual(flash_loan_args[1], opportunity['amount'])    # amount
        self.assertEqual(flash_loan_args[3], opportunity['gas_price']) # gas price

if __name__ == '__main__':
    unittest.main()
