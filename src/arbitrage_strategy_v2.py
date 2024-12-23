"""Enhanced Arbitrage Strategy for Mainnet V2"""
import json
from typing import Dict, Optional, Tuple
from decimal import Decimal
from web3 import Web3

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
from . import arb_calculations
from . import token_checks
from . import arb_execution

class EnhancedArbitrageStrategy(MEVStrategy):
    """Enhanced arbitrage strategy for mainnet with improved validation and safety checks."""
    
    def __init__(self, w3: Web3, config: Dict):
        """Initialize strategy with mainnet-specific configurations."""
        super().__init__(w3, config)
        
        try:
            # Initialize DEX handler
            self.dex_handler = DEXHandler(w3, config)
            
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
            arb_config = config.get('strategies', {}).get('arbitrage', {})
            self.min_profit_wei = int(arb_config.get(
                'min_profit_wei',
                mainnet.MIN_PROFIT_THRESHOLD
            ))
            self.max_position_size = int(arb_config.get(
                'max_position_size',
                mainnet.MAX_POSITION_SIZE
            ))
            
            # List of contracts that need token approvals
            self.contracts_to_check = [
                self.flash_loan_provider,
                self.uniswap_router,
                self.sushiswap_router,
                self.contract_address
            ]
            
            # Validate configuration
            self._validate_config()
            
            logger.info("Enhanced Arbitrage strategy V2 initialized with mainnet configuration")
            
        except Exception as e:
            logger.error(f"Error initializing arbitrage strategy: {e}")
            raise ConfigurationError(f"Failed to initialize strategy: {e}")
            
    def _load_abi(self, path: str):
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
            if self.min_profit_wei < mainnet.MIN_PROFIT_THRESHOLD:
                raise ConfigurationError("Minimum profit too low for mainnet")
            
            # Validate position sizes
            if self.max_position_size > mainnet.MAX_POSITION_SIZE:
                raise ConfigurationError("Maximum position size too high for mainnet")
                
            # Validate network
            chain_id = self.web3.eth.chain_id
            if chain_id != mainnet.MAINNET_CHAIN_ID:
                raise ConfigurationError(f"Invalid network. Expected mainnet (1), got chain_id: {chain_id}")
                
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ConfigurationError(f"Invalid mainnet configuration: {e}")

    async def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze transaction for arbitrage opportunity with mainnet-specific validation."""
        if not tx or not isinstance(tx, dict):
            return None
            
        try:
            # Decode swap data
            swap_data = self.dex_handler.decode_swap_data(tx)
            if not swap_data:
                return None
            
            # Get pool information
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
            if not mainnet.validate_pool_data(pool_data_uni) or not mainnet.validate_pool_data(pool_data_sushi):
                return None
            
            # Calculate optimal arbitrage
            arb_amount, profit = await arb_calculations.calculate_optimal_arbitrage(
                self,
                pool_data_uni,
                pool_data_sushi,
                swap_data['path'][0],
                swap_data['path'][1]
            )
            
            if not arb_amount or profit < self.min_profit_wei:
                return None
            
            # Calculate gas costs
            needs_approvals = not (
                await token_checks.check_token_allowance(
                    self.web3,
                    swap_data['path'][0],
                    self.token_abi,
                    self.account.address,
                    self.contracts_to_check,
                    self.web3.to_wei('1000000', 'ether')
                )
            )
            
            gas_estimate = mainnet.calculate_gas_estimate(needs_approvals)
            gas_price = await self.web3.eth.gas_price
            
            if not mainnet.validate_gas_price(gas_price):
                return None
            
            # Prepare callback data
            callback_data = self._encode_strategy_callback(
                'arbitrage',
                swap_data['path'][0],
                swap_data['path'][1],
                arb_amount,
                pool_data_uni['pair_address'],
                sushi_pool=pool_data_sushi['pair_address']
            )
            
            # Create opportunity
            opportunity = {
                'type': 'arbitrage',
                'token_in': swap_data['path'][0],
                'token_out': swap_data['path'][1],
                'amount': arb_amount,
                'profit': profit,
                'gas_price': gas_price,
                'gas_estimate': gas_estimate,
                'pools': {
                    'uniswap': pool_data_uni['pair_address'],
                    'sushiswap': pool_data_sushi['pair_address']
                },
                'callback_data': callback_data,
                'flash_loan_contract': self.contract_address,
                'timestamp': self.web3.eth.get_block('latest').timestamp
            }
            
            return opportunity
            
        except Exception as e:
            logger.error(f"Error analyzing arbitrage opportunity: {e}")
            return None

    async def execute_opportunity(self, opportunity: Dict) -> bool:
        """Execute arbitrage opportunity using flash loans through Flashbots."""
        try:
            # Validate execution conditions
            conditions_valid = await arb_execution.validate_execution_conditions(
                self.web3,
                opportunity,
                self.min_profit_wei,
                mainnet.MAX_GAS_PRICE
            )
            if not conditions_valid:
                return False
            
            # Execute arbitrage
            success, profit = await arb_execution.execute_arbitrage(
                self.web3,
                opportunity,
                self.contract_address,
                self.token_abi,
                self.web3.to_wei('1000000', 'ether'),
                self.account.address,
                self.contracts_to_check,
                self._execute_with_flash_loan
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing arbitrage opportunity: {e}")
            return False
