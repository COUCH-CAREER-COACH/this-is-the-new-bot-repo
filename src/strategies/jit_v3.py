"""Enhanced JIT Liquidity Strategy V3 for Mainnet"""
from typing import Dict, Optional, Tuple
from decimal import Decimal
import asyncio
import time
from web3 import Web3
from web3.exceptions import BlockNotFound

from ..logger_config import logger
from ..base_strategy import MEVStrategy
from ..utils.dex_handler import DEXHandler

class JITLiquidityStrategyV3(MEVStrategy):
    """Enhanced JIT liquidity strategy for mainnet trading"""
    
    def __init__(self, web3: Web3, config: Dict):
        """Initialize the JIT liquidity strategy."""
        super().__init__(web3, config)
        
        # Initialize DEX handler
        self.dex_handler = DEXHandler(web3, config)
        
        # Load JIT-specific configuration
        jit_config = config.get('strategies', {}).get('jit', {})
        
        # MEV competition parameters
        self.base_priority_fee = Web3.to_wei(2, 'gwei')  # Start at 2 GWEI
        self.max_priority_fee = Web3.to_wei(50, 'gwei')  # Cap at 50 GWEI
        self.priority_fee_multiplier = Decimal('1.5')
        
        # Dynamic gas configuration
        self.base_gas_add = Decimal('200000')  # Base gas for adding liquidity
        self.base_gas_remove = Decimal('150000')  # Base gas for removing liquidity
        self.gas_buffer_percent = Decimal('30')  # Higher buffer for mainnet
        
        # Profit thresholds
        self.min_profit_wei = Decimal(str(jit_config.get('min_profit_wei', '100000000000000000')))
        self.profit_margin_multiplier = Decimal('2.0')  # 100% margin over costs
        
        # Safety parameters
        self.max_position_size = Decimal(str(jit_config.get('max_position_size', '50000000000000000000')))
        self.max_price_impact = Decimal(str(jit_config.get('max_price_impact', '0.05')))
        self.slippage_tolerance = Decimal('0.02')  # 2% slippage tolerance
        self.liquidity_hold_blocks = int(jit_config.get('liquidity_hold_blocks', 2))
        
        # Competition monitoring
        self._recent_jits = []
        self._competition_level = Decimal('1.0')
        
        logger.info("Enhanced JIT Liquidity strategy V3 initialized with mainnet configuration")

    async def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze transaction for JIT liquidity opportunity."""
        if not tx or not isinstance(tx, dict):
            return None
            
        try:
            # Monitor competition levels
            await self._monitor_competition()
            
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
            
            # Validate JIT opportunity
            valid, message = await self._validate_jit_opportunity(tx, pool_data, swap_data)
            if not valid:
                logger.debug(f"JIT validation failed: {message}")
                return None
            
            # Calculate optimal liquidity amounts
            amount_a, amount_b = await self._calculate_optimal_liquidity(
                Decimal(str(swap_data['amountIn'])),
                pool_data
            )
            
            # Get current network conditions
            base_fee = Decimal(str((await self.web3.eth.get_block('latest'))['baseFeePerGas']))
            gas_price = await self._calculate_optimal_gas_price(base_fee)
            
            # Calculate potential profit
            profit = await self._calculate_potential_profit(
                amount_a,
                amount_b,
                swap_data,
                pool_data,
                gas_price
            )
            
            if profit < self.min_profit_wei:
                logger.debug(f"Insufficient profit: {profit} < {self.min_profit_wei}")
                return None
            
            return {
                'type': 'jit',
                'dex': swap_data['dex'],
                'token_a': pool_data['token0'],
                'token_b': pool_data['token1'],
                'amount_a': int(amount_a),
                'amount_b': int(amount_b),
                'pool_address': pool_data['pair_address'],
                'gas_price': int(gas_price),
                'expected_profit': int(profit),
                'competition_level': float(self._competition_level),
                'target_tx_hash': tx['hash'],
                'hold_blocks': self.liquidity_hold_blocks,
                'timestamp': int(time.time())
            }
            
        except Exception as e:
            logger.error(f"Error analyzing JIT opportunity: {e}")
            return None

    async def execute_opportunity(self, opportunity: Dict) -> bool:
        """Execute JIT liquidity opportunity using flash loans through Flashbots."""
        if not opportunity or opportunity['type'] != 'jit':
            return False
            
        try:
            # Prepare execution parameters
            execution_deadline = int(time.time() + 120)  # 2 minute deadline
            
            # Calculate total flash loan amount needed
            total_loan_amount = opportunity['amount_a']  # Borrow token A
            
            # Encode the JIT strategy callback for the flash loan
            callback_data = self._encode_strategy_callback(
                'jit',
                opportunity['token_a'],
                opportunity['token_b'],
                total_loan_amount,
                opportunity['pool_address'],
                amount_b=opportunity['amount_b'],
                hold_blocks=opportunity['hold_blocks']
            )
            
            # Execute the JIT strategy using flash loan through Flashbots
            success, profit = await self._execute_with_flash_loan(
                opportunity['token_a'],
                total_loan_amount,
                callback_data,
                opportunity['gas_price']
            )
            
            # Record result for competition monitoring
            self._recent_jits.append({
                'timestamp': time.time(),
                'success': success,
                'competition_level': float(self._competition_level)
            })
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing JIT opportunity: {e}")
            return False

    async def _monitor_competition(self) -> None:
        """Monitor and adjust for MEV competition."""
        try:
            # Clean old entries
            current_time = time.time()
            self._recent_jits = [j for j in self._recent_jits 
                               if current_time - j['timestamp'] < 300]  # Keep last 5 minutes
            
            if not self._recent_jits:
                self._competition_level = Decimal('1.0')
                return
            
            # Calculate success rate
            success_count = sum(1 for j in self._recent_jits if j['success'])
            total_count = len(self._recent_jits)
            success_rate = Decimal(str(success_count)) / Decimal(str(total_count))
            
            # Adjust competition level
            if success_rate < Decimal('0.3'):  # Less than 30% success
                self._competition_level = min(self._competition_level * Decimal('1.5'), Decimal('3.0'))
            elif success_rate > Decimal('0.7'):  # More than 70% success
                self._competition_level = max(self._competition_level / Decimal('1.2'), Decimal('1.0'))
                
        except Exception as e:
            logger.error(f"Error monitoring competition: {e}")

    async def _calculate_optimal_gas_price(self, base_fee: Decimal) -> Decimal:
        """Calculate optimal gas price based on competition."""
        try:
            # Get current priority fee stats
            priority_fees = []
            latest_block = await self.web3.eth.get_block('latest')
            for tx_hash in latest_block['transactions'][-20:]:  # Look at last 20 transactions
                tx = await self.web3.eth.get_transaction(tx_hash)
                if 'maxPriorityFeePerGas' in tx:
                    priority_fees.append(Decimal(str(tx['maxPriorityFeePerGas'])))
            
            if priority_fees:
                # Calculate competitive priority fee
                avg_priority_fee = sum(priority_fees) / Decimal(str(len(priority_fees)))
                required_priority_fee = avg_priority_fee * self._competition_level
                
                # Apply limits
                priority_fee = min(max(required_priority_fee, Decimal(str(self.base_priority_fee))), 
                                 Decimal(str(self.max_priority_fee)))
            else:
                priority_fee = Decimal(str(self.base_priority_fee))
            
            # Calculate total gas price
            return base_fee + priority_fee
            
        except Exception as e:
            logger.error(f"Error calculating gas price: {e}")
            return base_fee + Decimal(str(self.base_priority_fee))

    async def _validate_jit_opportunity(
        self,
        victim_tx: Dict,
        pool_data: Dict,
        swap_data: Dict
    ) -> Tuple[bool, str]:
        """Validate JIT opportunity with mainnet considerations."""
        try:
            # Check basic transaction validity
            if not all([victim_tx, pool_data, swap_data]):
                return False, "Missing required data"
            
            # Validate target amount
            target_amount = Decimal(str(swap_data['amountIn']))
            if target_amount > self.max_position_size:
                return False, "Target transaction too large"
            
            # Calculate and validate price impact
            price_impact = self.dex_handler.calculate_price_impact(
                int(target_amount),
                pool_data['reserves']['token0'],
                pool_data['reserves']['token1'],
                pool_data['fee']
            )
            
            if price_impact > self.max_price_impact:
                return False, f"Price impact too high: {price_impact}%"
            
            # Check pool liquidity
            total_liquidity = Decimal(str(pool_data['reserves']['token0'])) + Decimal(str(pool_data['reserves']['token1']))
            min_liquidity = target_amount * Decimal('20')  # Require 20x target amount in liquidity
            if total_liquidity < min_liquidity:
                return False, "Insufficient pool liquidity"
            
            # Validate gas price competitiveness
            target_gas_price = Decimal(str(victim_tx.get('gasPrice', 0)))
            if target_gas_price <= Decimal(str(self.base_priority_fee)):
                return False, "Target gas price too low"
            
            return True, "Valid JIT opportunity"
            
        except Exception as e:
            logger.error(f"Error validating JIT opportunity: {e}")
            return False, f"Validation error: {str(e)}"

    async def _calculate_optimal_liquidity(
        self,
        target_amount: Decimal,
        pool_data: Dict
    ) -> Tuple[Decimal, Decimal]:
        """Calculate optimal liquidity amounts."""
        try:
            # Get current pool price
            price = Decimal(str(pool_data['reserves']['token1'])) / Decimal(str(pool_data['reserves']['token0']))
            
            # Calculate base amounts (typically 50-150% of target amount)
            base_amount_a = target_amount * Decimal('0.5')  # Start with 50% of target amount
            base_amount_b = base_amount_a * price  # Equivalent amount of token B
            
            # Apply limits
            max_amount_a = min(
                target_amount * Decimal('1.5'),  # Max 150% of target amount
                Decimal(str(pool_data['reserves']['token0'])) * Decimal('0.1')  # Max 10% of pool reserves
            )
            max_amount_b = max_amount_a * price
            
            return min(base_amount_a, max_amount_a), min(base_amount_b, max_amount_b)
            
        except Exception as e:
            logger.error(f"Error calculating optimal liquidity: {e}")
            return Decimal('0'), Decimal('0')

    async def _calculate_potential_profit(
        self,
        amount_a: Decimal,
        amount_b: Decimal,
        swap_data: Dict,
        pool_data: Dict,
        gas_price: Decimal
    ) -> Decimal:
        """Calculate potential profit with mainnet considerations."""
        try:
            # Calculate gas costs for both adding and removing liquidity
            total_gas = (self.base_gas_add + self.base_gas_remove) * (
                Decimal('1') + self.gas_buffer_percent / Decimal('100'))
            total_gas_cost = total_gas * gas_price
            
            # Calculate expected fees from target transaction
            target_amount = Decimal(str(swap_data['amountIn']))
            fee_percentage = pool_data['fee']
            expected_fees = target_amount * fee_percentage
            
            # Calculate share of fees based on provided liquidity
            total_liquidity = Decimal(str(pool_data['reserves']['token0'])) + amount_a
            liquidity_share = amount_a / total_liquidity
            fee_share = expected_fees * liquidity_share
            
            # Calculate net profit
            gross_profit = fee_share
            net_profit = gross_profit - total_gas_cost
            
            # Apply safety margin
            safety_margin = Decimal('0.9')  # 10% safety margin
            return net_profit * safety_margin
            
        except Exception as e:
            logger.error(f"Error calculating potential profit: {e}")
            return Decimal('0')
