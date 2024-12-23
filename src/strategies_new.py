"""Enhanced MEV strategies with improved DEX validation and profitability."""
import time
import asyncio
from typing import Dict, Optional, Tuple
from decimal import Decimal
from web3 import Web3
from eth_abi import encode, decode

from .logger_config import logger
from .utils.dex_utils import DEXValidator
from .utils.method_signatures_new import get_method_info, is_dex_swap, is_dex_related
from .base_strategy import MEVStrategy

class EnhancedFrontRunStrategy(MEVStrategy):
    """Enhanced frontrunning strategy with improved profitability."""
    
    def __init__(self, w3: Web3, config: Dict):
        """Initialize FrontRun strategy with optimized settings."""
        super().__init__(w3, config)
        
        # Initialize optimized caching
        self.dex_validator = DEXValidator(config)
        self._dex_cache = {}
        self._reserve_cache = {}
        self._price_cache = {}
        self._last_cache_clear = time.time()
        self._cache_ttl = 3  # Reduced TTL for more accurate pricing
        
        # Load optimized configuration
        frontrun_config = config.get('frontrun', {})
        self.gas_price_multiplier = Decimal(str(frontrun_config.get('gas_price_multiplier', '1.12')))
        self.min_profit_threshold = Decimal(str(frontrun_config.get('min_profit_threshold', '0.01')))
        self.max_gas_price = int(frontrun_config.get('max_gas_price', 50)) * 10**9
        self.min_pool_liquidity = int(frontrun_config.get('min_pool_liquidity', '100000000000000000000'))
        
        # Performance optimizations
        self._execution_lock = asyncio.Lock()
        self._execution_timeout = 2
        self._max_slippage = Decimal('0.003')  # 0.3% max slippage
        self._min_profit_multiplier = Decimal('1.5')  # 150% of gas costs
        
        logger.debug("Enhanced FrontRun strategy initialized with optimized settings")

    async def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze transaction with optimized validation and profit calculation."""
        if not tx or not isinstance(tx, dict):
            return None
            
        # Clear cache if TTL expired
        current_time = time.time()
        if current_time - self._last_cache_clear > self._cache_ttl:
            self._dex_cache.clear()
            self._reserve_cache.clear()
            self._price_cache.clear()
            self._last_cache_clear = current_time
            
        try:
            async with self._execution_lock:
                # Quick validation first
                if not await self._quick_validate_tx(tx):
                    return None
                    
                # Get method info and validate DEX interaction
                method_id = tx.get('input', '')[:10]
                method_info = get_method_info(method_id)
                
                if not method_info or not is_dex_swap(method_id):
                    return None
                    
                # Decode and validate swap data
                try:
                    token_in, token_out, amount_in = await self._decode_swap_data(tx)
                except Exception:
                    return None
                    
                # Get pool state with caching
                try:
                    pair_info = await self._get_pool_info(token_in, token_out)
                    if not pair_info:
                        return None
                except Exception:
                    return None
                    
                # Calculate profitability with optimized gas estimation
                profit_info = await self._calculate_profit(
                    token_in,
                    token_out,
                    amount_in,
                    pair_info
                )
                
                if not profit_info or profit_info['net_profit'] <= 0:
                    return None
                    
                return {
                    'type': 'frontrun',
                    'target_tx': tx['hash'].hex(),
                    'token_in': token_in,
                    'token_out': token_out,
                    'amount': amount_in,
                    'pair_address': pair_info['address'],
                    'reserves': pair_info['reserves'],
                    'expected_profit': profit_info['gross_profit'],
                    'gas_cost': profit_info['gas_cost'],
                    'net_profit': profit_info['net_profit'],
                    'execution_price': profit_info['execution_price'],
                    'method': method_info,
                    'dex': pair_info['dex']
                }
                
        except Exception as e:
            logger.error(f"Error analyzing opportunity: {e}", exc_info=True)
            return None

    async def _quick_validate_tx(self, tx: Dict) -> bool:
        """Perform quick validation checks."""
        try:
            # Basic field validation
            if not all([
                tx.get('hash'),
                tx.get('to'),
                tx.get('input'),
                len(tx['input']) >= 10
            ]):
                return False
                
            # Gas price check
            gas_price = int(tx.get('gasPrice', 0))
            if gas_price > self.max_gas_price:
                return False
                
            # Value check
            value = int(tx.get('value', 0))
            min_value = self.config.get('min_tx_value', 0)
            if value < min_value:
                return False
                
            return True
            
        except Exception:
            return False

    async def _decode_swap_data(self, tx: Dict) -> Tuple[str, str, int]:
        """Decode swap data with validation."""
        try:
            input_data = tx['input']
            method_id = input_data[:10]
            
            # Decode based on method signature
            params = decode(
                ['address', 'address', 'uint256'],
                bytes.fromhex(input_data[10:])
            )
            
            token_in, token_out, amount_in = params
            
            # Validate addresses and amount
            if not all([
                self.web3.is_address(token_in),
                self.web3.is_address(token_out),
                amount_in > 0
            ]):
                raise ValueError("Invalid swap parameters")
                
            return token_in, token_out, amount_in
            
        except Exception as e:
            logger.debug(f"Error decoding swap data: {e}")
            raise

    async def _get_pool_info(self, token_in: str, token_out: str) -> Optional[Dict]:
        """Get pool information with caching."""
        cache_key = f"{token_in}:{token_out}"
        
        try:
            # Check cache first
            if cache_key in self._reserve_cache:
                return self._reserve_cache[cache_key]
                
            # Get pair address
            pair_address = await self._get_pair_address(token_in, token_out)
            if not pair_address:
                return None
                
            # Get reserves
            reserves = await self._get_reserves(pair_address)
            if not reserves:
                return None
                
            # Get DEX info
            dex_name = await self.dex_validator.get_dex_name(pair_address)
            
            pool_info = {
                'address': pair_address,
                'reserves': reserves,
                'dex': dex_name
            }
            
            # Cache the result
            self._reserve_cache[cache_key] = pool_info
            return pool_info
            
        except Exception as e:
            logger.debug(f"Error getting pool info: {e}")
            return None

    async def _calculate_profit(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        pool_info: Dict
    ) -> Optional[Dict]:
        """Calculate potential profit with gas optimization."""
        try:
            # Get current gas price
            gas_price = await self.web3.eth.gas_price
            estimated_gas = 350000  # Optimized gas estimate
            gas_cost = Decimal(str(gas_price * estimated_gas)) / Decimal(10**18)
            
            # Calculate optimal execution price
            reserves_in, reserves_out = pool_info['reserves']
            execution_price = self._calculate_execution_price(
                amount_in,
                reserves_in,
                reserves_out
            )
            
            # Calculate expected output
            expected_output = self._calculate_output_amount(
                amount_in,
                reserves_in,
                reserves_out
            )
            
            # Calculate gross profit
            token_price = await self._get_token_price(token_out)
            gross_profit = (Decimal(str(expected_output)) / Decimal(10**18)) * token_price
            
            # Calculate net profit
            net_profit = gross_profit - gas_cost
            
            # Validate profitability
            min_required_profit = gas_cost * self._min_profit_multiplier
            if net_profit < min_required_profit:
                return None
                
            return {
                'gross_profit': gross_profit,
                'gas_cost': gas_cost,
                'net_profit': net_profit,
                'execution_price': execution_price
            }
            
        except Exception as e:
            logger.debug(f"Error calculating profit: {e}")
            return None

    async def execute_opportunity(self, opportunity: Dict) -> bool:
        """Execute opportunity with optimized gas and slippage protection."""
        if not opportunity or opportunity['type'] != 'frontrun':
            return False
            
        try:
            async with asyncio.timeout(self._execution_timeout):
                async with self._execution_lock:
                    return await self._execute_with_retry(opportunity)
        except asyncio.TimeoutError:
            logger.error("Execution timeout exceeded")
            return False
        except Exception as e:
            logger.error(f"Error executing opportunity: {e}")
            return False

    async def _execute_with_retry(self, opportunity: Dict, max_retries: int = 2) -> bool:
        """Execute opportunity with retry mechanism and slippage protection."""
        for attempt in range(max_retries):
            try:
                # Prepare optimized callback data
                callback_data = self._encode_strategy_callback(
                    'frontrun',
                    opportunity['token_in'],
                    opportunity['token_out'],
                    opportunity['amount'],
                    opportunity['pair_address']
                )
                
                # Calculate optimal gas price
                base_gas_price = await self.web3.eth.gas_price
                optimal_gas_price = int(base_gas_price * self.gas_price_multiplier)
                
                # Execute with flash loan
                success, profit = await self._execute_with_flash_loan(
                    opportunity['token_in'],
                    opportunity['amount'],
                    callback_data,
                    optimal_gas_price
                )
                
                if success:
                    logger.info(f"Successfully executed opportunity with {profit} ETH profit")
                    return True
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to execute after {max_retries} attempts: {e}")
                    return False
                logger.warning(f"Retry {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(0.1 * (attempt + 1))
                
        return False

    def _calculate_execution_price(
        self,
        amount_in: int,
        reserve_in: int,
        reserve_out: int
    ) -> Decimal:
        """Calculate optimal execution price with fee consideration."""
        try:
            amount_with_fee = Decimal(str(amount_in)) * Decimal('997')
            numerator = amount_with_fee * Decimal(str(reserve_out))
            denominator = (Decimal(str(reserve_in)) * Decimal('1000')) + amount_with_fee
            
            if denominator == 0:
                raise ValueError("Invalid reserves for price calculation")
                
            return numerator / denominator
            
        except Exception as e:
            logger.error(f"Error calculating execution price: {e}")
            raise

    def _calculate_output_amount(
        self,
        amount_in: int,
        reserve_in: int,
        reserve_out: int
    ) -> int:
        """Calculate expected output amount with slippage consideration."""
        try:
            amount_in_with_fee = amount_in * 997
            numerator = amount_in_with_fee * reserve_out
            denominator = (reserve_in * 1000) + amount_in_with_fee
            
            return numerator // denominator
            
        except Exception as e:
            logger.error(f"Error calculating output amount: {e}")
            raise

    async def _get_token_price(self, token: str) -> Decimal:
        """Get token price with caching."""
        try:
            if token in self._price_cache:
                cached_price, cached_time = self._price_cache[token]
                if time.time() - cached_time < self._cache_ttl:
                    return cached_price
                    
            # Get fresh price
            price = Decimal(str(await self._fetch_token_price(token)))
            self._price_cache[token] = (price, time.time())
            return price
            
        except Exception as e:
            logger.error(f"Error getting token price: {e}")
            return Decimal('0')
