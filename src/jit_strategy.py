"""Just-In-Time Liquidity Strategy Implementation."""
import asyncio
from typing import Dict, Optional, List, Tuple, Any
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
from . import token_checks

class JustInTimeLiquidityStrategy(MEVStrategy):
    """Just-In-Time (JIT) liquidity provision strategy."""
    
    def __init__(self, w3: Web3, config: Dict[str, Any]):
        """Initialize JIT strategy."""
        super().__init__(w3, config)
        
        try:
            # Initialize DEX handler
            self.dex_handler = DEXHandler(w3, config)
            
            # Load JIT-specific configuration
            jit_config = config.get('strategies', {}).get('jit', {})
            self.min_profit_wei = int(jit_config.get(
                'min_profit_wei',
                mainnet.MIN_PROFIT_THRESHOLD
            ))
            self.max_position_size = int(jit_config.get(
                'max_position_size',
                mainnet.MAX_POSITION_SIZE
            ))
            self.max_blocks_to_wait = int(jit_config.get(
                'max_blocks_to_wait',
                2
            ))
            
            # Load contract ABIs
            self.token_abi = self._load_abi('contracts/interfaces/IERC20.json')
            self.pair_abi = self._load_abi('contracts/interfaces/IUniswapV2Pair.json')
            
            logger.info("JIT strategy initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing JIT strategy: {e}")
            raise ConfigurationError(f"Failed to initialize JIT strategy: {e}")

    async def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze transaction for JIT opportunity."""
        if not tx or not isinstance(tx, dict):
            return None
            
        try:
            # Decode swap data
            swap_data = self.dex_handler.decode_swap_data(tx)
            if not swap_data:
                return None
                
            # Get pool information
            pool_info = await self.dex_handler.get_pool_info(
                'uniswap',
                swap_data['path'][0],
                swap_data['path'][1]
            )
            
            # Validate pool data
            if not mainnet.validate_pool_data(pool_info):
                return None
                
            # Calculate optimal JIT position
            position_size, profit = await self._calculate_optimal_position(
                pool_info,
                swap_data['amount_in'],
                swap_data['path'][0],
                swap_data['path'][1]
            )
            
            if not position_size or profit < self.min_profit_wei:
                return None
                
            # Calculate gas costs
            needs_approvals = not (
                await token_checks.check_token_allowance(
                    self.web3,
                    swap_data['path'][0],
                    self.token_abi,
                    self.account.address,
                    [pool_info['pair_address']],
                    position_size
                )
            )
            
            gas_estimate = mainnet.calculate_gas_estimate(needs_approvals)
            gas_price = await self.web3.eth.gas_price
            
            if not mainnet.validate_gas_price(gas_price):
                return None
                
            # Create opportunity
            opportunity = {
                'type': 'jit',
                'token_in': swap_data['path'][0],
                'token_out': swap_data['path'][1],
                'amount': position_size,
                'profit': profit,
                'gas_price': gas_price,
                'gas_estimate': gas_estimate,
                'pool': pool_info['pair_address'],
                'deadline': swap_data['deadline'],
                'target_tx': tx['hash'],
                'timestamp': self.web3.eth.get_block('latest').timestamp
            }
            
            return opportunity
            
        except Exception as e:
            logger.error(f"Error analyzing JIT opportunity: {e}")
            return None

    async def execute_opportunity(self, opportunity: Dict) -> bool:
        """Execute JIT opportunity."""
        try:
            # Validate execution conditions
            conditions_valid = await self._validate_execution_conditions(opportunity)
            if not conditions_valid:
                return False
                
            # Execute JIT strategy
            success = await self._execute_jit_strategy(opportunity)
            if not success:
                return False
                
            # Monitor target transaction
            included = await self._monitor_target_transaction(
                opportunity['target_tx'],
                opportunity['deadline']
            )
            
            return included
            
        except Exception as e:
            logger.error(f"Error executing JIT opportunity: {e}")
            return False

    async def _calculate_optimal_position(
        self,
        pool_info: Dict,
        target_amount: int,
        token_in: str,
        token_out: str
    ) -> Tuple[Optional[int], Optional[int]]:
        """Calculate optimal JIT position size."""
        try:
            # Get current reserves
            reserves = pool_info['reserves']
            
            # Calculate optimal position using binary search
            min_amount = self.web3.to_wei(0.1, 'ether')  # 0.1 ETH minimum
            max_amount = min(
                int(reserves['token0'] * Decimal('0.2')),  # 20% of pool liquidity
                self.max_position_size
            )
            
            optimal_amount = None
            max_profit = 0
            
            while min_amount <= max_amount:
                amount = (min_amount + max_amount) // 2
                
                # Calculate expected profit
                try:
                    profit = await self._calculate_jit_profit(
                        amount,
                        target_amount,
                        reserves['token0'],
                        reserves['token1']
                    )
                    
                    if profit > max_profit:
                        max_profit = profit
                        optimal_amount = amount
                        min_amount = amount + 1  # Try larger amounts
                    else:
                        max_amount = amount - 1  # Try smaller amounts
                        
                except (InsufficientLiquidityError, ExcessiveSlippageError):
                    max_amount = amount - 1
                    
            return optimal_amount, max_profit
            
        except Exception as e:
            logger.error(f"Error calculating optimal position: {e}")
            return None, None

    async def _calculate_jit_profit(
        self,
        position_size: int,
        target_amount: int,
        reserve0: int,
        reserve1: int
    ) -> int:
        """Calculate expected profit from JIT position."""
        try:
            # Calculate price impact of target transaction
            price_impact = mainnet.calculate_price_impact(
                target_amount,
                reserve0,
                reserve1
            )
            
            if price_impact > self.max_slippage * 100:
                raise ExcessiveSlippageError("Price impact too high")
                
            # Calculate output amount
            amount_in_with_fee = int(target_amount * 997)  # 0.3% fee
            numerator = amount_in_with_fee * reserve1
            denominator = (reserve0 * 1000) + amount_in_with_fee
            amount_out = numerator // denominator
            
            # Calculate profit
            profit = amount_out - position_size
            
            if profit <= 0:
                raise InsufficientLiquidityError("No profit opportunity")
                
            return profit
            
        except Exception as e:
            logger.error(f"Error calculating JIT profit: {e}")
            raise

    async def _validate_execution_conditions(self, opportunity: Dict) -> bool:
        """Validate conditions before executing JIT strategy."""
        try:
            # Validate network connection
            if not await mainnet.validate_network(self.web3):
                return False
                
            # Validate gas price
            current_gas_price = await self.web3.eth.gas_price
            if current_gas_price > opportunity['gas_price'] * Decimal('1.1'):
                return False
                
            # Validate pool liquidity
            pool_contract = self.web3.eth.contract(
                address=opportunity['pool'],
                abi=self.pair_abi
            )
            
            reserves = await pool_contract.functions.getReserves().call()
            if reserves[0] < self.min_liquidity or reserves[1] < self.min_liquidity:
                return False
                
            # Validate deadline
            if self.web3.eth.get_block('latest').timestamp >= opportunity['deadline']:
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating execution conditions: {e}")
            return False

    async def _execute_jit_strategy(self, opportunity: Dict) -> bool:
        """Execute JIT liquidity provision."""
        try:
            # Add liquidity to pool
            pool_contract = self.web3.eth.contract(
                address=opportunity['pool'],
                abi=self.pair_abi
            )
            
            # Build transaction
            tx = await pool_contract.functions.mint(
                self.account.address
            ).build_transaction({
                'from': self.account.address,
                'gas': opportunity['gas_estimate'],
                'maxFeePerGas': opportunity['gas_price'],
                'maxPriorityFeePerGas': self.priority_fee,
                'nonce': await self.web3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send transaction
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = await self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            return receipt['status'] == 1
            
        except Exception as e:
            logger.error(f"Error executing JIT strategy: {e}")
            return False

    async def _monitor_target_transaction(
        self,
        target_tx: str,
        deadline: int
    ) -> bool:
        """Monitor target transaction inclusion."""
        try:
            start_block = self.web3.eth.block_number
            
            while self.web3.eth.block_number <= start_block + self.max_blocks_to_wait:
                try:
                    receipt = await self.web3.eth.get_transaction_receipt(target_tx)
                    if receipt:
                        return receipt['status'] == 1
                except Exception:
                    pass
                    
                if self.web3.eth.get_block('latest').timestamp >= deadline:
                    return False
                    
                await asyncio.sleep(1)
                
            return False
            
        except Exception as e:
            logger.error(f"Error monitoring target transaction: {e}")
            return False
