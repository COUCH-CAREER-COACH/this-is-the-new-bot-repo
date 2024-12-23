"""Test suite for sandwich strategy implementation with realistic mainnet conditions"""
import pytest
import asyncio
import time
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from web3 import Web3
from eth_utils import to_checksum_address

from src.sandwich_strategy_new import EnhancedSandwichStrategy
from src.mock_flash_loan import MockFlashLoan
from test.mocks import MockWeb3, MockDexHandler

# Constants for testing with real mainnet addresses
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI_ADDRESS = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
UNISWAP_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"

# Mainnet init code hashes
UNISWAP_INIT_CODE_HASH = "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f"
SUSHISWAP_INIT_CODE_HASH = "0xe18a34eb0e04b04f7a0ac29a6e80748dca96319b42c54d679cb821dca90c6303"
