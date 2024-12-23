"""Test arbitrage analysis with network-specific scenarios"""
import unittest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from web3 import Web3
import time

from src.arbitrage_strategy import EnhancedArbitrageStrategy
from src.exceptions import (
    ConfigurationError,
    InsufficientLiquidityError,
    ExcessiveSlippageError,
    GasEstimationError,
    ContractError
)

class TestArbNetwork(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.w3 = Mock(spec=Web3)
        self.w3.eth = Mock()
        self.w3.eth.contract = Mock()
        self.w3.eth.get_transaction_count = AsyncMock(return_value=0)
        self.w3.eth.gas_price = 50000000000  # 50 GWEI
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

    async def test_wrong_network(self):
        """Test handling of wrong network chain ID."""
        # Set chain ID to Ropsten (3)
        self.w3.eth.chain_id = 3

        with self.assertRaises(ConfigurationError):
            strategy = EnhancedArbitrageStrategy(self.w3, self.config)

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_network_congestion(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of network congestion (high gas, many pending txs)."""
        # Set high gas price indicating network congestion
        self.w3.eth.gas_price = 300000000000  # 300 GWEI
        self.w3.eth.max_priority_fee_per_gas = 30000000000  # 30 GWEI priority fee
        
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = {
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'
            ],
            'amountIn': 1000000000000000000
        }

        # Mock pools with good opportunity but high network activity
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000000,
                    'token1': 2000000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time()),
                'pending_txs': ['0x1', '0x2', '0x3']  # Many pending transactions
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000000,
                    'token1': 2400000000000000000000  # 20% price difference
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time()),
                'pending_txs': ['0x4', '0x5']
            }
        ]

        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000
        }

        result = await strategy.analyze_transaction(tx)
        self.assertIsNone(result, "Should reject opportunity during network congestion")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_mainnet_contract_validation(self, mock_get_pool_info, mock_decode_swap):
        """Test validation of contract deployment on mainnet."""
        # Mock contract code check to return empty bytes (no contract)
        self.w3.eth.get_code = Mock(return_value=b'')

        with self.assertRaises(ContractError):
            strategy = EnhancedArbitrageStrategy(self.w3, self.config)

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_flashbots_bundle_requirement(self, mock_get_pool_info, mock_decode_swap):
        """Test handling of opportunities requiring Flashbots bundles."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        mock_decode_swap.return_value = {
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'
            ],
            'amountIn': 10000000000000000000  # 10 ETH (large enough to require Flashbots)
        }

        # Mock pools with significant opportunity
        mock_get_pool_info.side_effect = [
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000000,
                    'token1': 2000000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': int(time.time())
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 1000000000000000000000,
                    'token1': 2400000000000000000000  # 20% price difference
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
        self.assertIsNotNone(result)
        self.assertTrue(result.get('requires_flashbots', False), "Large opportunities should require Flashbots")

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_mainnet_fork_detection(self, mock_get_pool_info, mock_decode_swap):
        """Test detection and handling of mainnet fork scenarios."""
        # Mock block timestamp far in the future (indicating potential fork)
        future_time = int(time.time()) + 86400  # 1 day in the future
        self.w3.eth.get_block = AsyncMock(return_value={'timestamp': future_time})
        
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
                'block_timestamp_last': future_time
            },
            {
                'pair_address': '0x1234567890123456789012345678901234567890',
                'reserves': {
                    'token0': 100000000000000000000,
                    'token1': 220000000000000000000
                },
                'fee': Decimal('0.003'),
                'block_timestamp_last': future_time
            }
        ]

        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000
        }

        result = await strategy.analyze_transaction(tx)
        self.assertIsNone(result, "Should reject opportunities on potential fork")

if __name__ == '__main__':
    unittest.main()
