"""Test arbitrage analysis edge cases and error handling"""
import unittest
from unittest.mock import patch, Mock, AsyncMock
from decimal import Decimal
import time
import pytest

from src.arbitrage_strategy import EnhancedArbitrageStrategy
from src.exceptions import (
    ConfigurationError,
    InsufficientLiquidityError,
    ExcessiveSlippageError,
    GasEstimationError,
    ContractError
)
from .test_config import (
    get_test_config,
    get_mock_web3,
    get_mock_contract,
    get_mock_pool_info,
    get_mock_swap_data,
    get_mock_transaction
)

class TestArbEdgeCases(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.w3 = get_mock_web3()
        self.config = get_test_config()
        self.w3.eth.contract.return_value = get_mock_contract()

    async def test_invalid_configuration(self):
        """Test handling of invalid configuration."""
        # Test with missing required config
        invalid_config = {
            'strategies': {},
            'dex': {},
            'flash_loan': {}
        }

        with self.assertRaises(ConfigurationError):
            strategy = EnhancedArbitrageStrategy(self.w3, invalid_config)

        # Test with invalid addresses
        invalid_address_config = self.config.copy()
        invalid_address_config['dex']['uniswap_v2_router'] = '0xinvalid'

        with self.assertRaises(ConfigurationError):
            strategy = EnhancedArbitrageStrategy(self.w3, invalid_address_config)

        # Test with invalid thresholds
        invalid_threshold_config = self.config.copy()
        invalid_threshold_config['strategies']['arbitrage']['min_profit_wei'] = '0'

        with self.assertRaises(ConfigurationError):
            strategy = EnhancedArbitrageStrategy(self.w3, invalid_threshold_config)

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    async def test_invalid_transaction_format(self, mock_decode_swap):
        """Test handling of invalid transaction formats."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Test with None transaction
        result = await strategy.analyze_transaction(None)
        self.assertIsNone(result, "Should handle None transaction")

        # Test with empty transaction
        result = await strategy.analyze_transaction({})
        self.assertIsNone(result, "Should handle empty transaction")

        # Test with missing required fields
        result = await strategy.analyze_transaction({'hash': '0x123'})
        self.assertIsNone(result, "Should handle transaction missing required fields")

        # Test with invalid input data
        result = await strategy.analyze_transaction({
            'hash': '0x123',
            'input': '0x',
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 0
        })
        self.assertIsNone(result, "Should handle transaction with invalid input data")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_contract_deployment_check(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of non-deployed contracts."""
        # Mock contract code check to return empty bytes (no contract)
        self.w3.eth.get_code = Mock(return_value=b'')

        with self.assertRaises(ContractError):
            strategy = EnhancedArbitrageStrategy(self.w3, self.config)

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_network_errors(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of network-related errors."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock network error in pool info
        mock_decode_swap.return_value = get_mock_swap_data()
        mock_get_pool_info.side_effect = Exception("Network error")

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should handle network errors gracefully")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_decimal_overflow(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of decimal overflow scenarios."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pools with extremely large numbers
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 2**256 - 1,  # Max uint256
                    'token1': 2**256 - 1
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 2**256 - 1,
                    'token1': 2**256 - 1
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should handle decimal overflow gracefully")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_zero_values(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of zero values in various fields."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Test with zero amount
        swap_data = get_mock_swap_data()
        swap_data['amountIn'] = 0
        mock_decode_swap.return_value = swap_data

        mock_get_pool_info.side_effect = [
            get_mock_pool_info(),
            get_mock_pool_info()
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should handle zero amount gracefully")

        # Test with zero reserves
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 0,
                    'token1': 0
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            get_mock_pool_info()
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should handle zero reserves gracefully")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_malformed_addresses(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of malformed addresses."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Test with invalid token addresses
        swap_data = get_mock_swap_data()
        swap_data['path'] = ['0xinvalid', '0xalsobad']
        mock_decode_swap.return_value = swap_data

        mock_get_pool_info.side_effect = [
            get_mock_pool_info(),
            get_mock_pool_info()
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should handle invalid addresses gracefully")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_future_timestamp(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of future timestamps in pool data."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pool with future timestamp
        future_time = int(time.time()) + 3600  # 1 hour in future
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 200000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': future_time
            },
            get_mock_pool_info()
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should reject data with future timestamps")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_negative_values(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of negative values (which shouldn't be possible but could occur from overflow)."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pool with negative values (from uint256 overflow)
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': -100000000000000000000,  # Negative value
                    'token1': 200000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            get_mock_pool_info()
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        self.assertIsNone(result, "Should handle negative values gracefully")

if __name__ == '__main__':
    unittest.main()
