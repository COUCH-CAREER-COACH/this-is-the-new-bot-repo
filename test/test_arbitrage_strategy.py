"""Tests for Enhanced Arbitrage Strategy"""
import unittest
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal
from web3 import Web3
import asyncio
import time

from src.arbitrage_strategy import EnhancedArbitrageStrategy
from src.utils.dex_utils import DEXHandler

class TestEnhancedArbitrageStrategy(unittest.TestCase):
    def setUp(self):
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
        
        # Mock Aave pool provider
        mock_contract.functions.getPool = Mock()
        mock_contract.functions.getPool.return_value = Mock()
        mock_contract.functions.getPool.return_value.call = AsyncMock(
            return_value="0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"
        )
        
        # Mock pool contract functions
        mock_contract.functions.getMaxFlashLoan = Mock()
        mock_contract.functions.getMaxFlashLoan.return_value = Mock()
        mock_contract.functions.getMaxFlashLoan.return_value.call = AsyncMock(
            return_value=1000000000000000000000  # 1000 ETH
        )
        
        # Mock flash loan functions
        mock_contract.functions.flashLoan = Mock()
        mock_contract.functions.flashLoan.return_value = Mock()
        mock_contract.functions.flashLoan.return_value.call = AsyncMock(return_value=True)
        mock_contract.functions.flashLoan.return_value.build_transaction = Mock(
            return_value={
                'to': '0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9',
                'data': '0x',
                'value': 0,
                'gas': 500000,
                'maxFeePerGas': 50000000000,
                'maxPriorityFeePerGas': 2000000000
            }
        )
        
        # Mock pair contract functions
        mock_contract.functions.getReserves = Mock()
        mock_contract.functions.getReserves.return_value = Mock()
        mock_contract.functions.getReserves.return_value.call = AsyncMock(
            return_value=[
                100000000000000000000,  # 100 ETH
                200000000000000000000,  # 200 tokens
                int(time.time())
            ]
        )
        
        # Mock factory contract functions
        mock_contract.functions.getPair = Mock()
        mock_contract.functions.getPair.return_value = Mock()
        mock_contract.functions.getPair.return_value.call = AsyncMock(
            return_value="0x0000000000000000000000000000000000000000"
        )
        
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

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_analyze_transaction_profitable(self, mock_get_pool_info, mock_decode_swap):
        """Test analyzing a profitable arbitrage opportunity."""
        # Mock transaction data
        tx = {
            'hash': '0x123',
            'input': '0x12345678'
        }
        
        # Mock swap data
        mock_decode_swap.return_value = {
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'   # DAI
            ],
            'amountIn': 1000000000000000000  # 1 ETH
        }
        
        # Mock pool data with price difference
        mock_get_pool_info.side_effect = [
            {  # Uniswap pool
                'pair_address': '0xuni',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 200000000000000000000   # 200 DAI
                },
                'fee': Decimal('0.003')
            },
            {  # Sushiswap pool
                'pair_address': '0xsushi',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 220000000000000000000   # 220 DAI (10% higher price)
                },
                'fee': Decimal('0.003')
            }
        ]
        
        # Mock gas price
        self.w3.eth.gas_price = 50000000000  # 50 GWEI
        
        # Test analysis
        result = await self.strategy.analyze_transaction(tx)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'arbitrage')
        self.assertTrue(result['profit'] > self.strategy.min_profit_wei)
        self.assertIn('uniswap', result['pools'])
        self.assertIn('sushiswap', result['pools'])

    @patch('src.utils.dex_utils.DEXHandler.decode_swap_data')
    @patch('src.utils.dex_utils.DEXHandler.get_pool_info')
    async def test_analyze_transaction_unprofitable(self, mock_get_pool_info, mock_decode_swap):
        """Test analyzing an unprofitable arbitrage opportunity."""
        # Mock transaction data
        tx = {
            'hash': '0x123',
            'input': '0x12345678'
        }
        
        # Mock swap data
        mock_decode_swap.return_value = {
            'dex': 'uniswap',
            'path': [
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                '0x6B175474E89094C44Da98b954EedeAC495271d0F'   # DAI
            ],
            'amountIn': 1000000000000000000  # 1 ETH
        }
        
        # Mock pool data with minimal price difference
        mock_get_pool_info.side_effect = [
            {  # Uniswap pool
                'pair_address': '0xuni',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 200000000000000000000   # 200 DAI
                },
                'fee': Decimal('0.003')
            },
            {  # Sushiswap pool
                'pair_address': '0xsushi',
                'reserves': {
                    'token0': 100000000000000000000,  # 100 ETH
                    'token1': 201000000000000000000   # 201 DAI (0.5% higher price)
                },
                'fee': Decimal('0.003')
            }
        ]
        
        # Mock gas price
        self.w3.eth.gas_price = 50000000000  # 50 GWEI
        
        # Test analysis
        result = await self.strategy.analyze_transaction(tx)
        
        # Verify result
        self.assertIsNone(result)

    @patch('src.base_strategy.MEVStrategy._execute_with_flash_loan')
    async def test_execute_opportunity_success(self, mock_execute_flash_loan):
        """Test successful execution of arbitrage opportunity."""
        # Mock opportunity
        opportunity = {
            'type': 'arbitrage',
            'token_in': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
            'token_out': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
            'amount': 1000000000000000000,  # 1 ETH
            'profit': 100000000000000000,   # 0.1 ETH
            'gas_price': 50000000000,       # 50 GWEI
            'pools': {
                'uniswap': '0xuni',
                'sushiswap': '0xsushi'
            }
        }
        
        # Mock flash loan execution
        mock_execute_flash_loan.return_value = (True, Decimal('0.1'))
        
        # Test execution
        result = await self.strategy.execute_opportunity(opportunity)
        
        # Verify result
        self.assertTrue(result)
        mock_execute_flash_loan.assert_called_once()

    @patch('src.base_strategy.MEVStrategy._execute_with_flash_loan')
    async def test_execute_opportunity_failure(self, mock_execute_flash_loan):
        """Test failed execution of arbitrage opportunity."""
        # Mock opportunity
        opportunity = {
            'type': 'arbitrage',
            'token_in': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
            'token_out': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
            'amount': 1000000000000000000,
            'profit': 100000000000000000,
            'gas_price': 50000000000,
            'pools': {
                'uniswap': '0xuni',
                'sushiswap': '0xsushi'
            }
        }
        
        # Mock flash loan execution failure
        mock_execute_flash_loan.return_value = (False, Decimal('0'))
        
        # Test execution
        result = await self.strategy.execute_opportunity(opportunity)
        
        # Verify result
        self.assertFalse(result)
        mock_execute_flash_loan.assert_called_once()

    async def test_calculate_optimal_arbitrage(self):
        """Test optimal arbitrage calculation."""
        # Test data
        pool_uni = {
            'pair_address': '0xuni',
            'reserves': {
                'token0': 100000000000000000000,  # 100 ETH
                'token1': 200000000000000000000   # 200 DAI
            },
            'fee': Decimal('0.003')
        }
        
        pool_sushi = {
            'pair_address': '0xsushi',
            'reserves': {
                'token0': 100000000000000000000,  # 100 ETH
                'token1': 220000000000000000000   # 220 DAI
            },
            'fee': Decimal('0.003')
        }
        
        token_in = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
        token_out = '0x6B175474E89094C44Da98b954EedeAC495271d0F'
        
        # Calculate optimal arbitrage
        amount, profit = await self.strategy._calculate_optimal_arbitrage(
            pool_uni,
            pool_sushi,
            token_in,
            token_out
        )
        
        # Verify results
        self.assertGreater(amount, 0)
        self.assertGreater(profit, 0)
        self.assertLess(amount, pool_uni['reserves']['token0'] // 3)
        self.assertLess(amount, pool_sushi['reserves']['token0'] // 3)

if __name__ == '__main__':
    unittest.main()
