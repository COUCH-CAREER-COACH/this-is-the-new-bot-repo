"""Test arbitrage analysis with different gas price scenarios"""
import unittest
from unittest.mock import patch
from decimal import Decimal
import time

from src.arbitrage_strategy import EnhancedArbitrageStrategy
from src.exceptions import GasEstimationError
from .test_config import (
    get_test_config,
    get_mock_web3,
    get_mock_contract,
    get_mock_pool_info,
    get_mock_swap_data,
    get_mock_transaction
)

class TestArbGasPrice(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.w3 = get_mock_web3()
        self.config = get_test_config()
        self.w3.eth.contract.return_value = get_mock_contract()

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_high_gas_price_rejection(self, mock_get_pool_info, mock_decode_swap):
        """Test that opportunities are rejected when gas price is too high."""
        # Set extremely high gas price
        self.w3.eth.gas_price = 1000000000000  # 1000 GWEI
        
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock swap data
        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pool data
        mock_get_pool_info.side_effect = [
            get_mock_pool_info(),
            {  # Pool with higher price
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 220000000000000000000  # 10% higher price
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should reject opportunity when gas price is too high")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_normal_gas_price_acceptance(self, mock_get_pool_info, mock_decode_swap):
        """Test that opportunities are accepted with normal gas prices."""
        # Set normal gas price
        self.w3.eth.gas_price = 50000000000  # 50 GWEI
        
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock swap data
        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pool data with good opportunity
        mock_get_pool_info.side_effect = [
            get_mock_pool_info(),
            {  # Pool with higher price
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 220000000000000000000  # 10% higher price
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNotNone(result, "Should accept opportunity with normal gas price")
        self.assertGreater(result['profit'], 0)

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_dynamic_gas_price_threshold(self, mock_get_pool_info, mock_decode_swap):
        """Test that gas price threshold adjusts based on potential profit."""
        # Set moderately high gas price
        self.w3.eth.gas_price = 200000000000  # 200 GWEI
        
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock swap data with larger amount
        swap_data = get_mock_swap_data()
        swap_data['amountIn'] = 10000000000000000000  # 10 ETH
        mock_decode_swap.return_value = swap_data

        # Mock pools with larger reserves and price difference
        mock_get_pool_info.side_effect = [
            {  # Large pool
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000000,  # 1000 ETH
                    'token1': 2000000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {  # Large pool with 20% higher price
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000000,
                    'token1': 2400000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        # Create transaction with larger amount
        tx = get_mock_transaction()
        tx['value'] = 10000000000000000000  # 10 ETH

        result = await strategy.analyze_transaction(tx)
        self.assertIsNotNone(result, "Should accept high-profit opportunity despite high gas")
        self.assertGreater(result['profit'], self.w3.eth.gas_price * 1000000, 
                          "Profit should exceed gas costs significantly")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_gas_price_spike_handling(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of sudden gas price spikes."""
        # Start with normal gas price
        self.w3.eth.gas_price = 50000000000  # 50 GWEI
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock swap data
        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pools with good opportunity
        mock_get_pool_info.side_effect = [
            get_mock_pool_info(),
            {  # Pool with higher price
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 220000000000000000000  # 10% higher price
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        # First check with normal gas price
        result1 = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNotNone(result1, "Should accept opportunity with normal gas price")

        # Simulate gas price spike
        self.w3.eth.gas_price = 800000000000  # 800 GWEI
        result2 = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result2, "Should reject same opportunity after gas price spike")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_priority_fee_consideration(self, mock_get_pool_info, mock_decode_swap):
        """Test that priority fees are properly considered in profitability calculation."""
        self.w3.eth.gas_price = 50000000000  # 50 GWEI base fee
        self.w3.eth.max_priority_fee_per_gas = 20000000000  # 20 GWEI priority fee
        
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock swap data
        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pools with marginal opportunity
        mock_get_pool_info.side_effect = [
            get_mock_pool_info(),
            {  # Pool with slightly higher price
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 205000000000000000000  # 2.5% higher price
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should reject marginally profitable opportunity when considering priority fees")

if __name__ == '__main__':
    unittest.main()
