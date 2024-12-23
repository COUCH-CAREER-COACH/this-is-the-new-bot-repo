"""Enhanced Arbitrage Strategy for Mainnet"""
import json
import time
import asyncio
from typing import Dict, Optional, Tuple, List, Union
from decimal import Decimal
from web3 import Web3
from web3.exceptions import (
    BlockNotFound,
    ContractLogicError,
    TransactionNotFound,
    InvalidAddress,
    ValidationError
)
from web3.types import TxParams, Wei

from .logger_config import logger
from .base_strategy import MEVStrategy
from .utils.dex_utils import DEXHandler
from .exceptions import (
    ConfigurationError,
    InsufficientLiquidityError,
    ExcessiveSlippageError,
    GasEstimationError,
    ContractError
)
from . import mainnet_helpers as mainnet

# Use mainnet constants and utilities
MAINNET_CHAIN_ID = mainnet.MAINNET_CHAIN_ID
MIN_ETH_LIQUIDITY = mainnet.MIN_ETH_LIQUIDITY
MAX_GAS_PRICE = mainnet.MAX_GAS_PRICE
MIN_PROFIT_THRESHOLD = mainnet.MIN_PROFIT_THRESHOLD
MAX_POSITION_SIZE = mainnet.MAX_POSITION_SIZE
MAX_PRICE_IMPACT = mainnet.MAX_PRICE_IMPACT
MAX_SLIPPAGE = mainnet.MAX_SLIPPAGE
MIN_GAS_BUFFER = mainnet.MIN_GAS_BUFFER
BASE_GAS_ESTIMATE = mainnet.BASE_TX_GAS

# Import mainnet validation functions
validate_price_deviation = mainnet.validate_price_deviation
validate_reserve_ratio = mainnet.validate_reserve_ratio
validate_data_age = mainnet.validate_data_age
calculate_required_profit = mainnet.calculate_required_profit
validate_pool_data = mainnet.validate_pool_data
calculate_gas_with_priority = mainnet.calculate_gas_with_priority
validate_gas_price = mainnet.validate_gas_price
validate_price_impact = mainnet.validate_price_impact
validate_pool_size = mainnet.validate_pool_size
is_profitable_after_gas = mainnet.is_profitable_after_gas
