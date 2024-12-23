import unittest
from unittest.mock import patch, MagicMock
from src.jit_strategy import JustInTimeLiquidityStrategy

class TestJustInTimeLiquidity(unittest.TestCase):

    @patch('src.jit_strategy.Web3')
    def setUp(self, MockWeb3):
        self.w3 = MockWeb3()
        self.config = {
            'jit': {
                'min_swap_amount': 50 * 10**18,
                'max_pool_impact': '0.1',
                'gas_limit_add_liquidity': 200000,
                'gas_limit_remove_liquidity': 200000,
                'swap_methods': ['0x12345678']  # Example method ID
            },
            'dex_addresses': ['0xabcdef']  # Example DEX address
        }
        self.jit_strategy = JustInTimeLiquidityStrategy(self.w3, self.config)

    def test_validate_jit_candidate_success(self):
        tx = {
            'hash': '0x123',
            'input': '0x12345678',
            'gasPrice': 1000000000,
            'value': 60 * 10**18,
            'to': '0xabcdef'
        }
        result = self.jit_strategy._validate_jit_candidate(tx)
        self.assertTrue(result)

    def test_validate_jit_candidate_failure(self):
        tx = {
            'hash': '0x123',
            'input': '0x12345678',
            'gasPrice': 1000000000,
            'value': 40 * 10**18,  # Below min_swap_amount
            'to': '0xabcdef'
        }
        result = self.jit_strategy._validate_jit_candidate(tx)
        self.assertFalse(result)

    @patch('src.jit_strategy.JustInTimeLiquidityStrategy._validate_jit_candidate')
    @patch('src.jit_strategy.JustInTimeLiquidityStrategy._simulate_jit_liquidity')
    def test_analyze_transaction_success(self, mock_simulate_jit, mock_validate_jit):
        tx = {'hash': '0x123', 'input': '0x12345678'}
        mock_validate_jit.return_value = True
        mock_simulate_jit.return_value = 100  # Simulated profit

        result = self.jit_strategy.analyze_transaction(tx)
        self.assertIsNotNone(result)
        self.assertEqual(result['expected_profit'], 100)

    @patch('src.jit_strategy.JustInTimeLiquidityStrategy._validate_jit_candidate')
    def test_analyze_transaction_failure(self, mock_validate_jit):
        tx = {'hash': '0x123', 'input': '0x12345678'}
        mock_validate_jit.return_value = False

        result = self.jit_strategy.analyze_transaction(tx)
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
