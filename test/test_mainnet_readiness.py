import unittest
from unittest.mock import patch, MagicMock
import logging

class TestMainnetReadiness(unittest.TestCase):

    @patch('src.bot.ArbitrageBot')
    def test_verify_mainnet_readiness_success(self, MockArbitrageBot):
        # Arrange
        mock_bot = MockArbitrageBot.return_value
        mock_bot.check_connection.return_value = True
        mock_bot.verify_contracts.return_value = True

        with patch('logging.getLogger') as mock_get_logger:
            logger = mock_get_logger.return_value
            from scripts.verify_mainnet_readiness import main

            # Act
            main()

            # Assert
            logger.info.assert_any_call("Verifying mainnet readiness...")
            logger.info.assert_any_call("Connected to the mainnet successfully.")
            logger.info.assert_any_call("All necessary contracts are verified.")

    @patch('src.bot.ArbitrageBot')
    def test_verify_mainnet_readiness_failure(self, MockArbitrageBot):
        # Arrange
        mock_bot = MockArbitrageBot.return_value
        mock_bot.check_connection.return_value = False
        mock_bot.verify_contracts.return_value = False

        with patch('logging.getLogger') as mock_get_logger:
            logger = mock_get_logger.return_value
            from scripts.verify_mainnet_readiness import main

            # Act
            main()

            # Assert
            logger.error.assert_any_call("Failed to connect to the mainnet.")
            logger.error.assert_any_call("Some contracts are not verified.")

if __name__ == "__main__":
    unittest.main()
