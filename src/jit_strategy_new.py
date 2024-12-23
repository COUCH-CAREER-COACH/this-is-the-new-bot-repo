"""Enhanced JIT Liquidity Strategy for Mainnet"""
from typing import Dict, Optional, Tuple
from decimal import Decimal
import asyncio
import time
from web3 import Web3
from web3.exceptions import BlockNotFound

from .logger_config import logger
from .base_strategy import MEVStrategy
from .utils.dex_utils import DEXHandler

class EnhancedJITStrategy(MEVStrategy):
    def __init__(self, w3: Web3, config: Dict):
        super().__init__(w3, config)
        
        # Initialize DEX handler
        self.dex_handler = DEXHandler(w3, config)
        
        # Load JIT-specific configuration
        jit_config = config.get('strategies', {}).get('jit_liquidity', {})
        
        # Dynamic timing configuration
        self.min_blocks_wait = 1
        self.max_blocks_wait = 3
        self.block_time_buffer = 2  # seconds
        
        # Dynamic gas configuration
        self.base_gas_add = 150000
        self.base_gas_remove = 100000
        self.gas_buffer_percent = 20
        
        # Pool configuration
        self.min_pool_liquidity = int(jit_config.get('min_pool_liquidity', '5000000000000000000000'))
        self.max_pool_impact = Decimal(str(jit_config.get('max_pool_impact', '0.1')))
        
        # Profit thresholds
        self.min_profit_wei = int(jit_config.get('min_profit_wei', '200000000000000000'))
        self.profit_margin_multiplier = Decimal('1.5')  # 50% margin over costs
        
        # Initialize monitoring
        self._last_block_time = None
        self._block_times = []
        
        logger.info("Enhanced JIT strategy initialized with mainnet configuration")

    async def _get_dynamic_block_time(self) -> float:
        """Calculate dynamic block time based on recent history."""
        try:
            current_block = await self.w3.eth.block_number
            current_block_data = await self.w3.eth.get_block(current_block)
            current_time = current_block_data['timestamp']
            
            if self._last_block_time:
                block_time = current_time - self._last_block_time
                self._block_times.append(block_time)
                if len(self._block_times) > 10:
                    self._block_times.pop(0)
            
            self._last_block_time = current_time
            
            if self._block_times:
                avg_block_time = sum(self._block_times) / len(self._block_times)
                return max(avg_block_time, 12)  # minimum 12 seconds
            
            return 12  # default to 12 seconds if no history
            
        except Exception as e:
            logger.error(f"Error calculating block time: {e}")
            return 12  # fallback to 12 seconds

    async def _estimate_dynamic_gas(self, action: str, pool_data: Dict) -> int:
        """Estimate gas needed for operations based on current network conditions."""
        try:
            # Get current network gas prices
            base_fee = await self.w3.eth.get_block('latest')
            base_fee = base_fee.get('baseFeePerGas', 0)
            
            # Calculate base gas based on action
            if action == 'add_liquidity':
                base_gas = self.base_gas_add
            elif action == 'remove_liquidity':
                base_gas = self.base_gas_remove
            else:
                base_gas = 200000  # fallback
            
            # Add buffer based on pool size and current network conditions
            pool_size = pool_data['reserves']['token0'] + pool_data['reserves']['token1']
            size_multiplier = min(Decimal(str(pool_size)) / Decimal('1000000000000000000'), 2)
            
            # Calculate final gas with buffer
            gas_with_buffer = int(base_gas * size_multiplier * (1 + self.gas_buffer_percent / 100))
            
            return gas_with_buffer
            
        except Exception as e:
            logger.error(f"Error estimating dynamic gas: {e}")
            return 300000  # fallback to conservative estimate

    async def _validate_pool_conditions(self, pool_data: Dict, amount: int) -> Tuple[bool, str]:
        """Validate pool conditions with dynamic thresholds."""
        try:
            # Check minimum liquidity
            total_liquidity = pool_data['reserves']['token0'] + pool_data['reserves']['token1']
            if total_liquidity < self.min_pool_liquidity:
                return False, "Insufficient pool liquidity"
            
            # Calculate and validate price impact
            price_impact = self.dex_handler.calculate_price_impact(
                amount,
                pool_data['reserves']['token0'],
                pool_data['reserves']['token1'],
                pool_data['fee']
            )
            
            if price_impact > self.max_pool_impact:
                return False, f"Price impact too high: {price_impact}%"
            
            # Validate pool composition
            reserve_ratio = Decimal(str(pool_data['reserves']['token0'])) / Decimal(str(pool_data['reserves']['token1']))
            if not Decimal('0.1') <= reserve_ratio <= Decimal('10'):
                return False, "Unbalanced pool reserves"
            
            return True, "Pool conditions valid"
            
        except Exception as e:
            logger.error(f"Error validating pool conditions: {e}")
            return False, f"Error in validation: {str(e)}"

    async def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze transaction for JIT opportunity with mainnet-specific validation."""
        if not tx or not isinstance(tx, dict):
            return None
            
        try:
            # Identify DEX and decode swap data
            swap_data = self.dex_handler.decode_swap_data(tx)
            if not swap_data:
                return None
            
            # Get pool information
            pool_data = await self.dex_handler.get_pool_info(
                swap_data['dex'],
                swap_data['path'][0],
                swap_data['path'][1]
            )
            if not pool_data:
                return None
            
            # Validate pool conditions
            valid, message = await self._validate_pool_conditions(pool_data, swap_data['amountIn'])
            if not valid:
                logger.debug(f"Pool validation failed: {message}")
                return None
            
            # Calculate optimal JIT parameters
            block_time = await self._get_dynamic_block_time()
            gas_estimate = await self._estimate_dynamic_gas('add_liquidity', pool_data)
            
            # Calculate potential profit
            profit = await self._calculate_potential_profit(
                swap_data,
                pool_data,
                gas_estimate,
                block_time
            )
            
            if profit < self.min_profit_wei:
                logger.debug(f"Insufficient profit: {profit} < {self.min_profit_wei}")
                return None
            
            return {
                'type': 'jit_liquidity',
                'dex': swap_data['dex'],
                'token_in': swap_data['path'][0],
                'token_out': swap_data['path'][1],
                'amount': swap_data['amountIn'],
                'pool_address': pool_data['pair_address'],
                'gas_estimate': gas_estimate,
                'block_time': block_time,
                'expected_profit': profit,
                'timestamp': int(time.time())
            }
            
        except Exception as e:
            logger.error(f"Error analyzing JIT opportunity: {e}")
            return None

    async def _calculate_potential_profit(
        self,
        swap_data: Dict,
        pool_data: Dict,
        gas_estimate: int,
        block_time: float
    ) -> int:
        """Calculate potential profit with mainnet considerations."""
        try:
            # Get current gas price
            gas_price = await self.w3.eth.gas_price
            
            # Calculate total gas cost
            total_gas_cost = gas_estimate * gas_price
            
            # Calculate fee earned from swap
            amount_in = Decimal(str(swap_data['amountIn']))
            fee_earned = amount_in * pool_data['fee']
            
            # Convert fee to Wei
            fee_earned_wei = int(fee_earned * Decimal('1000000000000000000'))
            
            # Calculate net profit
            net_profit = fee_earned_wei - total_gas_cost
            
            # Apply profit margin multiplier
            required_profit = int(total_gas_cost * self.profit_margin_multiplier)
            
            return max(net_profit, required_profit)
            
        except Exception as e:
            logger.error(f"Error calculating potential profit: {e}")
            return 0

    async def execute_opportunity(self, opportunity: Dict) -> bool:
        """Execute JIT opportunity with mainnet safety measures."""
        if not opportunity or opportunity['type'] != 'jit_liquidity':
            return False
            
        try:
            # Prepare execution parameters
            block_time = await self._get_dynamic_block_time()
            execution_deadline = int(time.time() + block_time * 2)
            
            # Prepare flash loan for liquidity
            flash_loan_amount = opportunity['amount']
            
            # Build transaction bundle
            add_liquidity_tx = await self._build_add_liquidity_tx(
                opportunity['token_in'],
                opportunity['token_out'],
                flash_loan_amount,
                opportunity['pool_address'],
                execution_deadline
            )
            
            remove_liquidity_tx = await self._build_remove_liquidity_tx(
                opportunity['pool_address'],
                flash_loan_amount,
                execution_deadline
            )
            
            # Execute through flashbots
            success = await self._execute_with_flashbots([
                add_liquidity_tx,
                remove_liquidity_tx
            ])
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing JIT opportunity: {e}")
            return False
