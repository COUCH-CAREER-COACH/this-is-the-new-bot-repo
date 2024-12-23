"""Comprehensive tests for arbitrage strategy"""
import unittest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from web3 import Web3
import time

from src.arbitrage_strategy import EnhancedArbitrageStrategy

def mock_to_wei(number, unit='ether'):
    """Mock Web3's to_wei function"""
    if unit == 'ether':
        return int(float(number) * 10**18)
    elif unit == 'gwei':
        return int(float(number) * 10**9)
    return int(number)

class TestArbStrategyV3(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create Web3 mock with proper async support
        self.w3 = Mock()
        self.w3.eth = Mock()
        self.w3.eth.contract = Mock()
        self.w3.eth.get_transaction_count = AsyncMock(return_value=0)
        self.w3.eth.gas_price = 50000000000  # 50 GWEI
        self.w3.eth.get_gas_price = AsyncMock(return_value=50000000000)  # Important for profitability check
        self.w3.eth.block_number = 1000000
        self.w3.eth.get_block = AsyncMock(return_value={'timestamp': int(time.time())})

        # Mock Web3 utils
        self.w3.to_wei = mock_to_wei
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
                    'min_profit_wei': '100000000000000000',  # 0.1 ETH
                    'max_position_size': '50000000000000000000',  # 50 ETH
                    'max_price_impact': '0.05'  # 5%
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

    @patch('web3.Web3.toWei', mock_to_wei)
    async def test_analyze_profitable_tx(self):
        """Test analysis of a profitable arbitrage opportunity."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock DEX handler methods
        strategy.dex_handler.decode_swap_data = Mock(return_value={
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'   # DAI
            ],
            'amountIn': 1000000000000000000  # 1 ETH
        })

        # Mock get_pool_info with different responses for each DEX
        uni_pool = {
            'pair_address': '0x1234567890123456789012345678901234567890',
            'reserves': {
                'token0': 100000000000000000000,  # 100 ETH
                'token1': 200000000000000000000   # 200 DAI
            },
            'fee': Decimal('0.003')
        }
        sushi_pool = {
            'pair_address': '0x1234567890123456789012345678901234567890',
            'reserves': {
                'token0': 100000000000000000000,  # 100 ETH
                'token1': 220000000000000000000   # 220 DAI (10% higher price)
            },
            'fee': Decimal('0.003')
        }

        async def mock_get_pool_info(dex, *args):
            return uni_pool if dex == 'uniswap' else sushi_pool

        strategy.dex_handler.get_pool_info = mock_get_pool_info

        # Mock simulate_swap_output to return profitable values
        async def mock_simulate_swap(*args):
            amount_in = args[0]
            return int(amount_in * 1.1)  # 10% profit

        strategy._simulate_swap_output = mock_simulate_swap

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
        self.assertGreater(result['profit'], self.config['strategies']['arbitrage']['min_profit_wei'])
        self.assertIn('pools', result)
        self.assertIn('uniswap', result['pools'])
        self.assertIn('sushiswap', result['pools'])

    @patch('web3.Web3.toWei', mock_to_wei)
    async def test_analyze_unprofitable_tx(self):
        """Test analysis of an unprofitable arbitrage opportunity."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock DEX handler methods
        strategy.dex_handler.decode_swap_data = Mock(return_value={
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'   # DAI
            ],
            'amountIn': 1000000000000000000  # 1 ETH
        })

        # Mock get_pool_info with similar prices (unprofitable)
        uni_pool = {
            'pair_address': '0x1234567890123456789012345678901234567890',
            'reserves': {
                'token0': 100000000000000000000,  # 100 ETH
                'token1': 200000000000000000000   # 200 DAI
            },
            'fee': Decimal('0.003')
        }
        sushi_pool = {
            'pair_address': '0x1234567890123456789012345678901234567890',
            'reserves': {
                'token0': 100000000000000000000,  # 100 ETH
                'token1': 200200000000000000000   # 200.2 DAI (0.1% difference)
            },
            'fee': Decimal('0.003')
        }

        async def mock_get_pool_info(dex, *args):
            return uni_pool if dex == 'uniswap' else sushi_pool

        strategy.dex_handler.get_pool_info = mock_get_pool_info

        # Mock simulate_swap_output to return unprofitable values
        async def mock_simulate_swap(*args):
            amount_in = args[0]
            return int(amount_in * 0.999)  # 0.1% loss

        strategy._simulate_swap_output = mock_simulate_swap

        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',  # swapExactTokensForTokens
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000  # 1 ETH
        }

        result = await strategy.analyze_transaction(tx)
        
        # Verify no opportunity was found due to insufficient profit
        self.assertIsNone(result)

    @patch('web3.Web3.toWei', mock_to_wei)
    async def test_analyze_invalid_tx(self):
        """Test analysis of invalid transactions."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Test with None transaction
        result = await strategy.analyze_transaction(None)
        self.assertIsNone(result)

        # Test with empty transaction
        result = await strategy.analyze_transaction({})
        self.assertIsNone(result)

        # Test with invalid DEX
        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',
            'to': '0x1234567890123456789012345678901234567890',  # Random address
            'value': 1000000000000000000
        }
        result = await strategy.analyze_transaction(tx)
        self.assertIsNone(result)

        # Test with failed pool info fetch
        strategy.dex_handler.decode_swap_data = Mock(return_value={
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'
            ],
            'amountIn': 1000000000000000000
        })
        strategy.dex_handler.get_pool_info = AsyncMock(return_value=None)
        
        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000
        }
        result = await strategy.analyze_transaction(tx)
        self.assertIsNone(result)

    @patch('web3.Web3.toWei', mock_to_wei)
    async def test_gas_price_profitability(self):
        """Test that high gas prices make opportunities unprofitable."""
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock DEX handler methods with profitable setup
        strategy.dex_handler.decode_swap_data = Mock(return_value={
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'
            ],
            'amountIn': 1000000000000000000
        })

        uni_pool = {
            'pair_address': '0x1234',
            'reserves': {
                'token0': 100000000000000000000,
                'token1': 200000000000000000000
            },
            'fee': Decimal('0.003')
        }
        sushi_pool = {
            'pair_address': '0x5678',
            'reserves': {
                'token0': 100000000000000000000,
                'token1': 220000000000000000000
            },
            'fee': Decimal('0.003')
        }

        async def mock_get_pool_info(dex, *args):
            return uni_pool if dex == 'uniswap' else sushi_pool

        strategy.dex_handler.get_pool_info = mock_get_pool_info

        async def mock_simulate_swap(*args):
            amount_in = args[0]
            return int(amount_in * 1.1)  # 10% profit

        strategy._simulate_swap_output = mock_simulate_swap

        tx = {
            'hash': '0x123',
            'input': '0x38ed1739',
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000
        }

        # Test with normal gas price
        self.w3.eth.get_gas_price = AsyncMock(return_value=50000000000)  # 50 GWEI
        result = await strategy.analyze_transaction(tx)
        self.assertIsNotNone(result)

        # Test with very high gas price
        self.w3.eth.get_gas_price = AsyncMock(return_value=500000000000)  # 500 GWEI
        result = await strategy.analyze_transaction(tx)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
