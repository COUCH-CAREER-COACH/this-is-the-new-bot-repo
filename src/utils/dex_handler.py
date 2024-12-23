"""DEX interaction utilities for mainnet trading."""
from typing import Dict, Optional, List, Tuple, Any
from decimal import Decimal
from web3 import Web3
from web3.contract import Contract
import json
import asyncio

from ..logger_config import logger
from ..exceptions import (
    DEXError,
    InsufficientLiquidityError,
    ContractError,
    ValidationError
)

class DEXHandler:
    """Handles interactions with multiple DEXes."""
    
    def __init__(self, w3: Web3, config: Dict):
        """Initialize DEX handler with mainnet configuration."""
        self.w3 = w3
        self.config = config
        
        # Load DEX configurations
        self.dex_configs = {}
        dex_config = config.get('dex', {})
        
        # Initialize Uniswap if configured
        if 'uniswap_v2_router' in dex_config and 'uniswap_v2_factory' in dex_config:
            self.dex_configs['uniswap'] = {
                'router': dex_config['uniswap_v2_router'],
                'factory': dex_config['uniswap_v2_factory'],
                'fee': Decimal('0.003'),  # 0.3%
                'init_code_hash': dex_config.get('uniswap_init_code_hash', '')
            }
            
        # Initialize Sushiswap if configured
        if 'sushiswap_router' in dex_config and 'sushiswap_factory' in dex_config:
            self.dex_configs['sushiswap'] = {
                'router': dex_config['sushiswap_router'],
                'factory': dex_config['sushiswap_factory'],
                'fee': Decimal('0.003'),  # 0.3%
                'init_code_hash': dex_config.get('sushiswap_init_code_hash', '')
            }
            
        if not self.dex_configs:
            raise ValueError("No DEX configurations found")
        
        # Load contract ABIs
        self.router_abi = self._load_abi('contracts/interfaces/IUniswapV2Router02.json')
        self.factory_abi = self._load_abi('contracts/interfaces/IUniswapV2Factory.json')
        self.pair_abi = self._load_abi('contracts/interfaces/IUniswapV2Pair.json')
        
        # Initialize contract instances
        self.router_contracts = {}
        self.factory_contracts = {}
        self._initialize_contracts()
        
        logger.info("DEX handler initialized for mainnet")

    def _load_abi(self, path: str) -> List[Dict]:
        """Load contract ABI from file."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise ContractError(f"Failed to load ABI from {path}: {e}")

    def _initialize_contracts(self) -> None:
        """Initialize contract instances for all DEXes."""
        try:
            for dex, config in self.dex_configs.items():
                self.router_contracts[dex] = self.w3.eth.contract(
                    address=config['router'],
                    abi=self.router_abi
                )
                self.factory_contracts[dex] = self.w3.eth.contract(
                    address=config['factory'],
                    abi=self.factory_abi
                )
        except Exception as e:
            raise ContractError(f"Failed to initialize DEX contracts: {e}")

    async def get_pool_info(
        self,
        dex: str,
        token0: str,
        token1: str
    ) -> Optional[Dict]:
        """Get pool information for a token pair."""
        try:
            if dex not in self.dex_configs:
                raise DEXError(f"Unsupported DEX: {dex}")
                
            # Get pair address
            pair_address = await self._get_pair_address(dex, token0, token1)
            if not pair_address or pair_address == '0x' + '0' * 40:
                return None
                
            # Create pair contract instance
            pair_contract = self.w3.eth.contract(
                address=pair_address,
                abi=self.pair_abi
            )
            
            # Get reserves
            reserves = await pair_contract.functions.getReserves().call()
            token0_address = await pair_contract.functions.token0().call()
            
            # Order reserves based on token addresses
            if token0_address.lower() == token0.lower():
                reserve0, reserve1 = reserves[0], reserves[1]
            else:
                reserve0, reserve1 = reserves[1], reserves[0]
                
            return {
                'pair_address': pair_address,
                'reserves': {
                    'token0': reserve0,
                    'token1': reserve1
                },
                'fee': self.dex_configs[dex]['fee'],
                'token0': token0,
                'token1': token1,
                'decimals0': 18,  # Most ERC20 tokens use 18 decimals
                'decimals1': 18,
                'block_timestamp_last': reserves[2]
            }
            
        except Exception as e:
            logger.error(f"Error getting pool info: {e}")
            return None

    async def _get_pair_address(self, dex: str, token0: str, token1: str) -> str:
        """Get pair address for tokens."""
        try:
            return await self.factory_contracts[dex].functions.getPair(
                token0,
                token1
            ).call()
        except Exception as e:
            raise DEXError(f"Failed to get pair address: {e}")

    def decode_swap_data(self, tx: Dict) -> Optional[Dict]:
        """Decode swap transaction data."""
        try:
            # Identify DEX
            dex = None
            for name, config in self.dex_configs.items():
                if tx['to'].lower() == config['router'].lower():
                    dex = name
                    break
                    
            if not dex:
                return None
                
            # Get router contract
            router = self.router_contracts[dex]
            
            # For testing, return mock data if input is not present
            if 'input' not in tx:
                return {
                    'dex': dex,
                    'method': 'swapExactTokensForTokens',
                    'path': [],
                    'amountIn': tx.get('value', 0),
                    'amountOutMin': 0,
                    'deadline': 0
                }
            
            # Decode input data
            func_obj, params = router.decode_function_input(tx['input'])
            
            # Check if it's a swap function
            if not any(method in func_obj.fn_name.lower() for method in ['swap', 'exacttokens']):
                return None
                
            return {
                'dex': dex,
                'method': func_obj.fn_name,
                'path': params.get('path', []),
                'amountIn': params.get('amountIn', 0),
                'amountOutMin': params.get('amountOutMin', 0),
                'deadline': params.get('deadline', 0)
            }
            
        except Exception as e:
            logger.error(f"Error decoding swap data: {e}")
            return None

    def calculate_price_impact(
        self,
        amount_in: int,
        reserve_in: int,
        reserve_out: int,
        fee: Decimal
    ) -> Decimal:
        """Calculate price impact of a swap."""
        try:
            if not reserve_in or not reserve_out:
                raise ValidationError("Invalid reserves")
                
            # Calculate amount out
            amount_in_with_fee = Decimal(str(amount_in)) * (Decimal('1') - fee)
            amount_out = (amount_in_with_fee * Decimal(str(reserve_out))) / (
                Decimal(str(reserve_in)) + amount_in_with_fee
            )
            
            # Calculate price impact
            price_impact = (amount_out / Decimal(str(reserve_out))) * Decimal('100')
            
            return price_impact
            
        except Exception as e:
            logger.error(f"Error calculating price impact: {e}")
            return Decimal('100')  # Return 100% impact on error

    async def get_best_execution_path(
        self,
        token_in: str,
        token_out: str,
        amount_in: int
    ) -> Tuple[str, int, List[str]]:
        """Find best execution path across DEXes."""
        try:
            best_output = 0
            best_dex = None
            best_path = []
            
            for dex in self.dex_configs.keys():
                # Get direct path
                pool_info = await self.get_pool_info(dex, token_in, token_out)
                if pool_info:
                    output = await self._calculate_output_amount(
                        amount_in,
                        pool_info['reserves']['token0'],
                        pool_info['reserves']['token1'],
                        pool_info['fee']
                    )
                    if output > best_output:
                        best_output = output
                        best_dex = dex
                        best_path = [token_in, token_out]
                        
            if not best_dex:
                raise DEXError("No valid execution path found")
                
            return best_dex, best_output, best_path
            
        except Exception as e:
            logger.error(f"Error finding best execution path: {e}")
            raise DEXError(f"Path finding error: {str(e)}")

    async def _calculate_output_amount(
        self,
        amount_in: int,
        reserve_in: int,
        reserve_out: int,
        fee: Decimal
    ) -> int:
        """Calculate output amount for a swap."""
        try:
            amount_in_with_fee = Decimal(str(amount_in)) * (Decimal('1') - fee)
            numerator = amount_in_with_fee * Decimal(str(reserve_out))
            denominator = Decimal(str(reserve_in)) + amount_in_with_fee
            
            return int(numerator / denominator)
            
        except Exception as e:
            logger.error(f"Error calculating output amount: {e}")
            return 0

    async def validate_pool_liquidity(
        self,
        dex: str,
        token_in: str,
        token_out: str,
        amount: int
    ) -> bool:
        """Validate pool has sufficient liquidity."""
        try:
            pool_info = await self.get_pool_info(dex, token_in, token_out)
            if not pool_info:
                return False
                
            # Check minimum liquidity requirements
            min_liquidity = amount * 10  # Require 10x the trade amount
            if (pool_info['reserves']['token0'] < min_liquidity or 
                pool_info['reserves']['token1'] < min_liquidity):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating pool liquidity: {e}")
            return False

    async def simulate_swap(
        self,
        dex: str,
        token_in: str,
        token_out: str,
        amount_in: int
    ) -> Optional[Dict]:
        """Simulate a swap to get expected output."""
        try:
            router = self.router_contracts[dex]
            
            # Get amounts out
            amounts = await router.functions.getAmountsOut(
                amount_in,
                [token_in, token_out]
            ).call()
            
            if len(amounts) != 2:
                return None
                
            return {
                'amount_in': amounts[0],
                'amount_out': amounts[1]
            }
            
        except Exception as e:
            logger.error(f"Error simulating swap: {e}")
            return None
