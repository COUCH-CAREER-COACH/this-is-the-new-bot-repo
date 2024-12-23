"""Enhanced Arbitrage Strategy for Mainnet with improved validation and safety checks."""
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

class EnhancedArbitrageStrategy(MEVStrategy):
    """Enhanced arbitrage strategy for mainnet with improved validation and safety checks."""
    
    def __init__(self, w3: Web3, config: Dict):
        """Initialize strategy with mainnet-specific configurations."""
        super().__init__(w3, config)
        
        try:
            # Initialize DEX handler
            self.dex_handler = DEXHandler(w3, config)
            
            # Load arbitrage-specific configuration
            arb_config = config.get('strategies', {}).get('arbitrage', {})
            
            # Load contract addresses
            dex_config = config.get('dex', {})
            self.uniswap_router = self.web3.to_checksum_address(
                dex_config.get('uniswap_v2_router')
            )
            self.sushiswap_router = self.web3.to_checksum_address(
                dex_config.get('sushiswap_router')
            )
            
            # Load flash loan configuration
            flash_config = config.get('flash_loan', {})
            self.flash_loan_provider = self.web3.to_checksum_address(
                flash_config.get('providers', {}).get('aave', {}).get('pool_address_provider')
            )
            
            # Load contract ABIs
            self.token_abi = self._load_abi('contracts/interfaces/IERC20.json')
            self.arbitrage_abi = self._load_abi('contracts/FlashLoanArbitrage.json')
            
            # Initialize mainnet-specific parameters
            self.min_profit_wei = int(arb_config.get(
                'min_profit_wei',
                MIN_PROFIT_THRESHOLD
            ))
            self.max_position_size = int(arb_config.get(
                'max_position_size',
                MAX_POSITION_SIZE
            ))
            self.max_price_impact = Decimal(str(arb_config.get(
                'max_price_impact',
                MAX_PRICE_IMPACT
            )))
            self.slippage_tolerance = MAX_SLIPPAGE
            
            # Validate configuration
            self._validate_config()
            
            logger.info("Enhanced Arbitrage strategy initialized with mainnet configuration")
            
        except Exception as e:
            logger.error(f"Error initializing arbitrage strategy: {e}")
            raise ConfigurationError(f"Failed to initialize strategy: {e}")
            
    def _load_abi(self, path: str) -> List:
        """Load and validate contract ABI."""
        try:
            with open(path, 'r') as f:
                abi = json.load(f)
            if not isinstance(abi, list):
                raise ValueError(f"Invalid ABI format in {path}")
            return abi
        except Exception as e:
            raise ValueError(f"Error loading ABI from {path}: {e}")

    def _validate_config(self):
        """Validate strategy configuration for mainnet deployment."""
        try:
            # Validate contract addresses
            required_addresses = {
                'Uniswap Router': self.uniswap_router,
                'Sushiswap Router': self.sushiswap_router,
                'Flash Loan Provider': self.flash_loan_provider
            }
            
            for name, address in required_addresses.items():
                if not address or not self.web3.is_address(address):
                    raise ConfigurationError(f"Invalid {name} address: {address}")
                    
                # Verify contract code exists on mainnet
                code = self.web3.eth.get_code(address)
                if code == b'' or code == '0x':
                    raise ConfigurationError(f"No contract code found at {name} address: {address}")
            
            # Validate profit thresholds
            if self.min_profit_wei < MIN_PROFIT_THRESHOLD:
                raise ConfigurationError("Minimum profit too low for mainnet")
            
            # Validate position sizes
            if self.max_position_size > MAX_POSITION_SIZE:
                raise ConfigurationError("Maximum position size too high for mainnet")
                
            # Validate price impact and slippage settings
            if self.max_price_impact > MAX_PRICE_IMPACT:
                raise ConfigurationError("Price impact threshold too high for mainnet")
            if self.slippage_tolerance > MAX_SLIPPAGE:
                raise ConfigurationError("Slippage tolerance too high for mainnet")
                
            # Validate network
            chain_id = self.web3.eth.chain_id
            if chain_id != MAINNET_CHAIN_ID:
                raise ConfigurationError(f"Invalid network. Expected mainnet (1), got chain_id: {chain_id}")
                
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ConfigurationError(f"Invalid mainnet configuration: {e}")

    async def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze transaction for arbitrage opportunity with mainnet-specific validation."""
        if not tx or not isinstance(tx, dict):
            logger.debug("Invalid transaction format")
            return None
            
        try:
            # Identify DEX and decode swap data
            swap_data = self.dex_handler.decode_swap_data(tx)
            if not swap_data:
                logger.debug("Failed to decode swap data")
                return None
            
            logger.debug(f"Decoded swap data: {swap_data}")
            
            # Get pool information for both DEXes
            pool_data_uni = await self.dex_handler.get_pool_info(
                'uniswap',
                swap_data['path'][0],
                swap_data['path'][1]
            )
            
            pool_data_sushi = await self.dex_handler.get_pool_info(
                'sushiswap',
                swap_data['path'][0],
                swap_data['path'][1]
            )
            
            # Validate pool data
            if not validate_pool_data(pool_data_uni) or not validate_pool_data(pool_data_sushi):
                logger.debug("Invalid pool data")
                return None
            
            # Calculate optimal arbitrage amount
            arb_amount, profit = await self._calculate_optimal_arbitrage(
                pool_data_uni,
                pool_data_sushi,
                swap_data['path'][0],
                swap_data['path'][1]
            )
            
            if not arb_amount or profit < self.min_profit_wei:
                logger.debug(f"Insufficient profit: {profit} < {self.min_profit_wei}")
                return None
            
            # Get current gas price and validate
            gas_price = await self.web3.eth.gas_price
            if not validate_gas_price(gas_price):
                logger.debug(f"Gas price too high: {gas_price / 10**9:.2f} GWEI")
                return None
            
            # Calculate gas costs with priority fee
            priority_fee = await self.web3.eth.max_priority_fee_per_gas
            needs_approvals = not (
                await self._check_token_allowance(swap_data['path'][0]) and
                await self._check_token_allowance(swap_data['path'][1])
            )
            estimated_gas = mainnet.calculate_gas_estimate(needs_approvals)
            gas_cost = calculate_gas_with_priority(estimated_gas, gas_price, priority_fee)
            
            # Validate profitability
            if not is_profitable_after_gas(profit, gas_cost, gas_price):
                logger.debug("Not profitable after gas costs")
                return None
            
            # Create arbitrage result
            result = {
                'type': 'arbitrage',
                'token_in': swap_data['path'][0],
                'token_out': swap_data['path'][1],
                'amount': arb_amount,
                'profit': profit,
                'gas_price': gas_price,
                'pools': {
                    'uniswap': pool_data_uni['pair_address'],
                    'sushiswap': pool_data_sushi['pair_address']
                },
                'timestamp': int(time.time())
            }
            
            logger.debug(f"Found arbitrage opportunity: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing arbitrage opportunity: {e}")
            return None
