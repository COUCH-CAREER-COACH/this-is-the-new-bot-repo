"""Test arbitrage analysis with different liquidity scenarios"""
import unittest
from unittest.mock import patch
from decimal import Decimal
import time

from src.arbitrage_strategy import EnhancedArbitrageStrategy
from src.exceptions import InsufficientLiquidityError
from .test_config import (
    get_test_config,
    get_mock_web3,
    get_mock_contract,
    get_mock_pool_info,
    get_mock_swap_data,
    get_mock_transaction
)

class TestArbLiquidity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.w3 = get_mock_web3()
        self.config = get_test_config()
        self.w3.eth.contract.return_value = get_mock_contract()

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_insufficient_liquidity(self, mock_get_pool_info, mock_decode_swap):
        """Test that opportunities are rejected when pool liquidity is too low."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pools with very low liquidity
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000,  # Only 1 ETH
                    'token1': 2000000000000000000   # Only 2 DAI
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000,
                    'token1': 2200000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should reject opportunity when liquidity is insufficient")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_imbalanced_liquidity(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of pools with imbalanced liquidity."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pools with imbalanced liquidity
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,    # 100 ETH
                    'token1': 1000000000000000000000000 # 1M DAI (severe imbalance)
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 180000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should reject opportunity with severely imbalanced liquidity")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_optimal_liquidity(self, mock_get_pool_info, mock_decode_swap):
        """Test that opportunities are accepted with optimal liquidity."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pools with optimal liquidity
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000000,  # 1000 ETH
                    'token1': 2000000000000000000000   # 2000 DAI
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000000,
                    'token1': 2200000000000000000000  # 10% higher price
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNotNone(result, "Should accept opportunity with optimal liquidity")
        self.assertGreater(result['profit'], 0)

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_liquidity_threshold_scaling(self, mock_get_pool_info, mock_decode_swap):
        """Test that liquidity requirements scale with trade size."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock swap data with large amount
        swap_data = get_mock_swap_data()
        swap_data['amountIn'] = 50000000000000000000  # 50 ETH
        mock_decode_swap.return_value = swap_data

        # Mock pools with moderate liquidity (insufficient for large trade)
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 200000000000000000000   # 200 DAI
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 220000000000000000000  # 10% higher price
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        # Create transaction with larger amount
        tx = get_mock_transaction()
        tx['value'] = 50000000000000000000  # 50 ETH

        result = await strategy.analyze_transaction(tx)
        self.assertIsNone(result, "Should reject large trade with insufficient liquidity")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_dynamic_liquidity_requirements(self, mock_get_pool_info, mock_decode_swap):
        """Test that liquidity requirements adjust based on market conditions."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pools with high volatility (requires more liquidity)
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,   # 100 ETH
                    'token1': 150000000000000000000    # Volatile price
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 250000000000000000000    # Large price difference
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should reject opportunity in volatile conditions with moderate liquidity")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_liquidity_depth_analysis(self, mock_get_pool_info, mock_decode_swap):
        """Test analysis of liquidity depth across price levels."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pools with good top-level liquidity but poor depth
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 200000000000000000000   # 200 DAI
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 220000000000000000000  # 10% higher price
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time()),
                'pending_txs': ['0x1', '0x2']  # Pending transactions affecting depth
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should reject opportunity with poor liquidity depth")

if __name__ == '__main__':
    unittest.main()
