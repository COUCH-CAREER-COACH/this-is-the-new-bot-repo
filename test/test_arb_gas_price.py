"""Test arbitrage analysis with different gas price scenarios"""
import unittest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from web3 import Web3
import time

from src.arbitrage_strategy import EnhancedArbitrageStrategy
from src.exceptions import GasEstimationError

class TestArbGasPrice(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.w3 = Mock(spec=Web3)
        self.w3.eth = Mock()
        self.w3.eth.contract = Mock()
        self.w3.eth.get_transaction_count = AsyncMock(return_value=0)
        self.w3.eth.block_number = 1000000
        self.w3.eth.get_block = AsyncMock(return_value={'timestamp': int(time.time())})
        self.w3.eth.chain_id = 1  # Mainnet
        self.w3.eth.get_code = Mock(return_value=b'some_code')
        self.w3.eth.max_priority_fee_per_gas = 2000000000  # 2 GWEI

        # Mock Web3 utils
        self.w3.to_wei = Web3.to_wei
        self.w3.from_wei = Web3.from_wei
        self.w3.is_address = Web3.is_address
        self.w3.keccak = Web3.keccak
        self.w3.to_checksum_address = Web3.to_checksum_address

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
                'uniswap_init_code_hash': '0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f',
                'sushiswap_router': '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',
                'sushiswap_factory': '0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac',
                'sushiswap_init_code_hash': '0xe18a34eb0e04b04f7a0ac29a6e80748dca96319b42c54d679cb821dca90c6303'
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

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_high_gas_price_rejection(self, mock_get_pool_info, mock_decode_swap):
        """Test that opportunities are rejected when gas price is too high."""
        # Set extremely high gas price
        self.w3.eth.gas_price = 1000000000000  # 1000 GWEI
        
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = {
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'   # DAI
            ],
            'amountIn': 1000000000000000000
        }

        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 200000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 220000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000
        }

        result = await strategy.analyze_transaction(tx)
        self.assertIsNone(result, "Should reject opportunity when gas price is too high")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_normal_gas_price_acceptance(self, mock_get_pool_info, mock_decode_swap):
        """Test that opportunities are accepted with normal gas prices."""
        # Set normal gas price
        self.w3.eth.gas_price = 50000000000  # 50 GWEI
        
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = {
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'
            ],
            'amountIn': 1000000000000000000
        }

        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 200000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 220000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000
        }

        result = await strategy.analyze_transaction(tx)
        self.assertIsNotNone(result, "Should accept opportunity with normal gas price")
        self.assertGreater(result['profit'], 0)

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_dynamic_gas_price_threshold(self, mock_get_pool_info, mock_decode_swap):
        """Test that gas price threshold adjusts based on potential profit."""
        # Set moderately high gas price
        self.w3.eth.gas_price = 200000000000  # 200 GWEI
        
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = {
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'
            ],
            'amountIn': 10000000000000000000  # 10 ETH (larger amount)
        }

        # Mock pools with larger price difference for higher potential profit
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000000,  # 1000 ETH
                    'token1': 2000000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000000,
                    'token1': 2400000000000000000000  # 20% higher price
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            }
        ]

        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 10000000000000000000
        }

        result = await strategy.analyze_transaction(tx)
        self.assertIsNotNone(result, "Should accept high-profit opportunity despite high gas")
        self.assertGreater(result['profit'], self.w3.eth.gas_price * 1000000, "Profit should exceed gas costs significantly")

if __name__ == '__main__':
    unittest.main()
