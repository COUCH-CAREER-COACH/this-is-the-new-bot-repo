"""Mock tests for arbitrage strategy"""
import unittest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from web3 import Web3
import time

from src.arbitrage_strategy import EnhancedArbitrageStrategy

class TestArbMock(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create Web3 mock
        self.w3 = Mock()
        self.w3.eth = Mock()
        self.w3.eth.contract = Mock()
        self.w3.eth.get_transaction_count = AsyncMock(return_value=0)
        self.w3.eth.gas_price = 50000000000  # 50 GWEI
        self.w3.eth.block_number = 1000000
        self.w3.eth.get_block = AsyncMock(return_value={'timestamp': int(time.time())})

        # Mock Web3 utils
        self.w3.to_wei = lambda x, y: int(float(x) * 10**18 if y == 'ether' else float(x) * 10**9)
        self.w3.from_wei = Web3.from_wei
        self.w3.is_address = Web3.is_address
        self.w3.keccak = Web3.keccak

        # Mock contract setup
        mock_contract = Mock()
        mock_contract.functions = Mock()
        mock_contract.functions.getPool = Mock(return_value=Mock(call=Mock(return_value="0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9")))
        mock_contract.functions.getMaxFlashLoan = Mock(return_value=Mock(call=Mock(return_value=1000000000000000000000)))
        mock_contract.address = "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"
        self.w3.eth.contract.return_value = mock_contract

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

    @patch('web3.Web3.to_wei')
    async def test_analyze_profitable_tx(self, mock_to_wei):
        """Test analysis of a profitable arbitrage opportunity."""
        # Setup Web3.to_wei mock
        mock_to_wei.side_effect = lambda x, y: int(float(x) * 10**18 if y == 'ether' else float(x) * 10**9)

        # Initialize strategy
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock DEX handler methods
        strategy.dex_handler.decode_swap_data = AsyncMock(return_value={
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'   # DAI
            ],
            'amountIn': 1000000000000000000  # 1 ETH
        })

        # Mock get_pool_info with different responses for each DEX
        async def mock_get_pool_info(dex, *args):
            if dex == 'uniswap':
                return {
                    'pair_address': '0x1234567890123456789012345678901234567890',
                    'reserves': {
                        'token0': 100000000000000000000,  # 100 ETH
                        'token1': 200000000000000000000   # 200 DAI
                    },
                    'fee': Decimal('0.003')
                }
            else:
                return {
                    'pair_address': '0x1234567890123456789012345678901234567890',
                    'reserves': {
                        'token0': 100000000000000000000,  # 100 ETH
                        'token1': 220000000000000000000   # 220 DAI
                    },
                    'fee': Decimal('0.003')
                }
        strategy.dex_handler.get_pool_info = mock_get_pool_info

        # Mock optimal arbitrage calculation
        async def mock_calc_arb(*args):
            return (1000000000000000000, 100000000000000000)  # 1 ETH, 0.1 ETH profit
        strategy._calculate_optimal_arbitrage = mock_calc_arb

        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',  # swapExactTokensForTokens
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000  # 1 ETH
        }

        result = await strategy.analyze_transaction(tx)
        
        # Verify analysis result
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'arbitrage')
        self.assertEqual(result['token_in'], '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')
        self.assertEqual(result['token_out'], '0x6B175474E89094C44Da98b954EedeAC495271d0F')
        self.assertGreater(result['profit'], 0)
        self.assertIn('pools', result)
        self.assertIn('uniswap', result['pools'])
        self.assertIn('sushiswap', result['pools'])

    @patch('web3.Web3.to_wei')
    async def test_analyze_unprofitable_tx(self, mock_to_wei):
        """Test analysis of an unprofitable arbitrage opportunity."""
        # Setup Web3.to_wei mock
        mock_to_wei.side_effect = lambda x, y: int(float(x) * 10**18 if y == 'ether' else float(x) * 10**9)

        # Initialize strategy
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock DEX handler methods
        strategy.dex_handler.decode_swap_data = AsyncMock(return_value={
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'   # DAI
            ],
            'amountIn': 1000000000000000000  # 1 ETH
        })

        # Mock get_pool_info with similar prices (unprofitable)
        async def mock_get_pool_info(dex, *args):
            if dex == 'uniswap':
                return {
                    'pair_address': '0x1234567890123456789012345678901234567890',
                    'reserves': {
                        'token0': 100000000000000000000,  # 100 ETH
                        'token1': 200000000000000000000   # 200 DAI
                    },
                    'fee': Decimal('0.003')
                }
            else:
                return {
                    'pair_address': '0x1234567890123456789012345678901234567890',
                    'reserves': {
                        'token0': 100000000000000000000,  # 100 ETH
                        'token1': 200200000000000000000   # 200.2 DAI (0.1% difference)
                    },
                    'fee': Decimal('0.003')
                }
        strategy.dex_handler.get_pool_info = mock_get_pool_info

        # Mock optimal arbitrage calculation - no profitable opportunity
        async def mock_calc_arb(*args):
            return (0, 0)
        strategy._calculate_optimal_arbitrage = mock_calc_arb

        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',  # swapExactTokensForTokens
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000  # 1 ETH
        }

        result = await strategy.analyze_transaction(tx)
        
        # Verify no opportunity was found due to insufficient profit
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
