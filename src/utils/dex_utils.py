"""DEX interaction utilities."""
from typing import Dict, Optional, List, Tuple, Any
from decimal import Decimal
from web3 import Web3
import json
import asyncio

from ..logger_config import logger
from ..exceptions import (
    DEXError,
    ValidationError,
    InsufficientLiquidityError
)

class DEXHandler:
    """Handles DEX interactions and calculations."""
    
    def __init__(self, w3: Web3, config: Dict[str, Any]):
        """Initialize DEX handler."""
        self.w3 = w3
        self.config = config
        
        try:
            # Load DEX configurations
            self.uniswap_router = self.w3.to_checksum_address(
                config['dex']['uniswap_v2_router']
            )
            self.uniswap_factory = self.w3.to_checksum_address(
                config['dex']['uniswap_v2_factory']
            )
            self.sushiswap_router = self.w3.to_checksum_address(
                config['dex']['sushiswap_router']
            )
            self.sushiswap_factory = self.w3.to_checksum_address(
                config['dex']['sushiswap_factory']
            )
            
            # Load ABIs
            self.router_abi = self._load_abi('contracts/interfaces/IUniswapV2Router02.json')
            self.factory_abi = self._load_abi('contracts/interfaces/IUniswapV2Factory.json')
            self.pair_abi = self._load_abi('contracts/interfaces/IUniswapV2Pair.json')
            
            # Initialize contracts
            self.uniswap_router_contract = self.w3.eth.contract(
                address=self.uniswap_router,
                abi=self.router_abi
            )
            self.uniswap_factory_contract = self.w3.eth.contract(
                address=self.uniswap_factory,
                abi=self.factory_abi
            )
            self.sushiswap_router_contract = self.w3.eth.contract(
                address=self.sushiswap_router,
                abi=self.router_abi
            )
            self.sushiswap_factory_contract = self.w3.eth.contract(
                address=self.sushiswap_factory,
                abi=self.factory_abi
            )
            
            # Initialize cache
            self.pool_cache = {}
            self.price_cache = {}
            self.pool_cache_time = int(config['dex'].get('pool_cache_time', 30))
            self.price_cache_time = int(config['dex'].get('price_cache_time', 1))
            
            logger.info("DEX handler initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing DEX handler: {e}")
            raise DEXError(f"Failed to initialize DEX handler: {e}")

    def _load_abi(self, path: str) -> List[Dict]:
        """Load contract ABI from file."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise DEXError(f"Failed to load ABI from {path}: {e}")

    async def get_pool_info(
        self,
        dex: str,
        token0: str,
        token1: str
    ) -> Dict[str, Any]:
        """Get pool information for token pair."""
        try:
            # Check cache first
            cache_key = f"{dex}_{token0}_{token1}"
            cached_info = self.pool_cache.get(cache_key)
            if cached_info and cached_info['timestamp'] + self.pool_cache_time > self.w3.eth.get_block('latest').timestamp:
                return cached_info['data']
                
            # Get factory contract
            factory_contract = self.uniswap_factory_contract if dex == 'uniswap' else self.sushiswap_factory_contract
            
            # Get pair address
            pair_address = await factory_contract.functions.getPair(token0, token1).call()
            if pair_address == '0x' + '0' * 40:
                raise DEXError(f"No {dex} pool exists for {token0}/{token1}")
                
            # Get pair contract
            pair_contract = self.w3.eth.contract(
                address=pair_address,
                abi=self.pair_abi
            )
            
            # Get reserves
            reserves = await pair_contract.functions.getReserves().call()
            token0_decimals = await self._get_token_decimals(token0)
            token1_decimals = await self._get_token_decimals(token1)
            
            # Format pool info
            pool_info = {
                'pair_address': pair_address,
                'reserves': {
                    'token0': reserves[0],
                    'token1': reserves[1]
                },
                'decimals': {
                    'token0': token0_decimals,
                    'token1': token1_decimals
                },
                'last_update': reserves[2]
            }
            
            # Cache result
            self.pool_cache[cache_key] = {
                'data': pool_info,
                'timestamp': self.w3.eth.get_block('latest').timestamp
            }
            
            return pool_info
            
        except Exception as e:
            logger.error(f"Error getting pool info: {e}")
            raise DEXError(f"Failed to get pool info: {e}")

    async def _get_token_decimals(self, token: str) -> int:
        """Get token decimals."""
        try:
            token_contract = self.w3.eth.contract(
                address=token,
                abi=[{
                    'inputs': [],
                    'name': 'decimals',
                    'outputs': [{'type': 'uint8', 'name': ''}],
                    'stateMutability': 'view',
                    'type': 'function'
                }]
            )
            return await token_contract.functions.decimals().call()
        except Exception:
            return 18  # Default to 18 decimals

    def decode_swap_data(self, tx: Dict) -> Optional[Dict]:
        """Decode swap transaction data."""
        try:
            if not tx or 'input' not in tx:
                return None
                
            # Check if transaction is to a supported router
            if tx['to'] not in [self.uniswap_router, self.sushiswap_router]:
                return None
                
            # Get router contract
            router_contract = self.uniswap_router_contract if tx['to'] == self.uniswap_router else self.sushiswap_router_contract
            
            try:
                # Try to decode function call
                func_obj, params = router_contract.decode_function_input(tx['input'])
                
                # Check if it's a swap function
                if not any(name in func_obj.fn_name.lower() for name in ['swap', 'exact']):
                    return None
                    
                # Extract path
                path = params.get('path', [])
                if not path or len(path) < 2:
                    return None
                    
                # Format swap data
                swap_data = {
                    'function': func_obj.fn_name,
                    'path': path,
                    'amount_in': params.get('amountIn', 0),
                    'amount_out_min': params.get('amountOutMin', 0),
                    'deadline': params.get('deadline', 0)
                }
                
                return swap_data
                
            except Exception:
                return None
                
        except Exception as e:
            logger.error(f"Error decoding swap data: {e}")
            return None

    async def get_amounts_out(
        self,
        dex: str,
        amount_in: int,
        path: List[str]
    ) -> List[int]:
        """Get output amounts for a given input amount and path."""
        try:
            # Get router contract
            router_contract = self.uniswap_router_contract if dex == 'uniswap' else self.sushiswap_router_contract
            
            # Get amounts out
            amounts = await router_contract.functions.getAmountsOut(
                amount_in,
                path
            ).call()
            
            return amounts
            
        except Exception as e:
            logger.error(f"Error getting amounts out: {e}")
            raise DEXError(f"Failed to get amounts out: {e}")

    async def get_amounts_in(
        self,
        dex: str,
        amount_out: int,
        path: List[str]
    ) -> List[int]:
        """Get input amounts for a given output amount and path."""
        try:
            # Get router contract
            router_contract = self.uniswap_router_contract if dex == 'uniswap' else self.sushiswap_router_contract
            
            # Get amounts in
            amounts = await router_contract.functions.getAmountsIn(
                amount_out,
                path
            ).call()
            
            return amounts
            
        except Exception as e:
            logger.error(f"Error getting amounts in: {e}")
            raise DEXError(f"Failed to get amounts in: {e}")

    async def check_pool_liquidity(
        self,
        dex: str,
        token0: str,
        token1: str,
        min_liquidity: int
    ) -> bool:
        """Check if pool has sufficient liquidity."""
        try:
            # Get pool info
            pool_info = await self.get_pool_info(dex, token0, token1)
            
            # Check reserves
            if pool_info['reserves']['token0'] < min_liquidity or \
               pool_info['reserves']['token1'] < min_liquidity:
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking pool liquidity: {e}")
            return False

    async def simulate_swap(
        self,
        dex: str,
        amount_in: int,
        path: List[str],
        slippage_tolerance: Decimal
    ) -> Tuple[bool, int]:
        """Simulate swap and check slippage."""
        try:
            # Get expected output
            amounts = await self.get_amounts_out(dex, amount_in, path)
            expected_out = amounts[-1]
            
            # Calculate minimum output with slippage
            min_out = int(Decimal(str(expected_out)) * (1 - slippage_tolerance))
            
            # Get pool info for first and last tokens
            pool_info = await self.get_pool_info(dex, path[0], path[-1])
            
            # Calculate price impact
            price_impact = (Decimal(str(amount_in)) / Decimal(str(pool_info['reserves']['token0']))) * 100
            
            return price_impact <= slippage_tolerance * 100, min_out
            
        except Exception as e:
            logger.error(f"Error simulating swap: {e}")
            raise DEXError(f"Failed to simulate swap: {e}")

    async def monitor_pool(
        self,
        dex: str,
        token0: str,
        token1: str,
        callback: Any
    ) -> None:
        """Monitor pool for changes."""
        try:
            # Get pool info
            pool_info = await self.get_pool_info(dex, token0, token1)
            pair_contract = self.w3.eth.contract(
                address=pool_info['pair_address'],
                abi=self.pair_abi
            )
            
            # Create event filter
            sync_filter = pair_contract.events.Sync.create_filter(
                fromBlock='latest'
            )
            
            # Monitor events
            while True:
                events = sync_filter.get_new_entries()
                for event in events:
                    await callback(event)
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error monitoring pool: {e}")
            raise DEXError(f"Failed to monitor pool: {e}")
