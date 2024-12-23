"""Test arbitrage transaction analysis"""
import unittest
from unittest.mock import patch
from decimal import Decimal
import time

from src.arbitrage_strategy import EnhancedArbitrageStrategy
from .test_config import (
    get_test_config,
    get_mock_web3,
    get_mock_contract,
    get_mock_pool_info,
    get_mock_swap_data,
    get_mock_transaction
)

class TestArbAnalysis(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.w3 = get_mock_web3()
        self.config = get_test_config()
        self.w3.eth.contract.return_value = get_mock_contract()

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_analyze_profitable_transaction(self, mock_get_pool_info, mock_decode_swap):
        """Test analysis of a profitable arbitrage opportunity."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock swap data
        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pool data with significant price difference
        mock_get_pool_info.side_effect = [
            {  # Uniswap pool
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 200000000000000000000   # 200 DAI
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {  # Sushiswap pool with 10% higher price
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 220000000000000000000   # 220 DAI
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        
        # Verify analysis result
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'arbitrage')
        self.assertEqual(result['token_in'], '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')
        self.assertEqual(result['token_out'], '0x6B175474E89094C44Da98b954EedeAC495271d0F')
        self.assertGreater(result['profit'], 0)
        self.assertIn('pools', result)
        self.assertIn('uniswap', result['pools'])
        self.assertIn('sushiswap', result['pools'])

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_analyze_unprofitable_transaction(self, mock_get_pool_info, mock_decode_swap):
        """Test analysis of an unprofitable arbitrage opportunity."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock swap data
        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pool data with minimal price difference (unprofitable)
        mock_get_pool_info.side_effect = [
            {  # Uniswap pool
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 200000000000000000000   # 200 DAI
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {  # Sushiswap pool with 0.1% higher price (too small for profit)
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 200200000000000000000   # 200.2 DAI
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        
        # Verify no opportunity was found due to insufficient profit
        self.assertIsNone(result)

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_analyze_stale_pool_data(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of stale pool data."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock swap data
        mock_decode_swap.return_value = get_mock_swap_data()

        # Mock pools with stale timestamps
        stale_timestamp = int(time.time()) - 600  # 10 minutes old
        mock_get_pool_info.side_effect = [
            get_mock_pool_info(timestamp=stale_timestamp),
            get_mock_pool_info(timestamp=stale_timestamp)
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        
        # Verify opportunity was rejected due to stale data
        self.assertIsNone(result)

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_analyze_high_price_impact(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of opportunities with high price impact."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock swap data with large amount
        swap_data = get_mock_swap_data()
        swap_data['amountIn'] = 50000000000000000000  # 50 ETH
        mock_decode_swap.return_value = swap_data

        # Mock pools with normal liquidity (making 50 ETH trade too impactful)
        mock_get_pool_info.side_effect = [
            get_mock_pool_info(),
            get_mock_pool_info()
        ]

        result = await strategy.analyze_transaction(get_mock_transaction())
        
        # Verify opportunity was rejected due to high price impact
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
