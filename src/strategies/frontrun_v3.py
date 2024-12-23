"""Enhanced Frontrun Strategy V3 for Mainnet"""
from typing import Dict, Optional, Tuple
from decimal import Decimal
import asyncio
import time
from web3 import Web3
from web3.exceptions import BlockNotFound

from ..logger_config import logger
from ..base_strategy import MEVStrategy
from ..utils.dex_handler import DEXHandler

class FrontrunStrategyV3(MEVStrategy):
    """Enhanced frontrun strategy for mainnet trading"""
    
    def __init__(self, web3: Web3, config: Dict):
        """Initialize the frontrun strategy."""
        super().__init__(web3, config)
        
        # Initialize DEX handler
        self.dex_handler = DEXHandler(web3, config)
        
        # Load frontrun-specific configuration
        frontrun_config = config.get('strategies', {}).get('frontrun', {})
        
        # MEV competition parameters
        self.base_priority_fee = Web3.to_wei(2, 'gwei')  # Start at 2 GWEI
        self.max_priority_fee = Web3.to_wei(50, 'gwei')  # Cap at 50 GWEI
        self.priority_fee_multiplier = Decimal('1.5')
        
        # Dynamic gas configuration
        self.base_gas = Decimal('180000')  # Base gas for frontrun tx
        self.gas_buffer_percent = Decimal('30')  # Higher buffer for mainnet
        
        # Profit thresholds
        self.min_profit_wei = Decimal(str(frontrun_config.get('min_profit_wei', '100000000000000000')))
        self.profit_margin_multiplier = Decimal('2.0')  # 100% margin over costs
        
        # Safety parameters
        self.max_position_size = Decimal(str(frontrun_config.get('max_position_size', '50000000000000000000')))
        self.max_price_impact = Decimal(str(frontrun_config.get('max_price_impact', '0.05')))
        self.slippage_tolerance = Decimal('0.02')  # 2% slippage tolerance
        
        # Competition monitoring
        self._recent_frontruns = []
        self._competition_level = Decimal('1.0')
        
        logger.info("Enhanced Frontrun strategy V3 initialized with mainnet configuration")

    async def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze transaction for frontrun opportunity."""
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
            
            # Validate frontrun opportunity
            valid, message = await self._validate_frontrun_opportunity(tx, pool_data, swap_data)
            if not valid:
                logger.debug(f"Frontrun validation failed: {message}")
                return None
            
            # Calculate optimal amount
            frontrun_amount = await self._calculate_optimal_amount(
                Decimal(str(swap_data['amountIn'])),
                Decimal(str(pool_data['reserves']['token0'])),
                Decimal(str(pool_data['reserves']['token1'])),
                pool_data['fee']
            )
            
            # Get current network conditions
            base_fee = Decimal(str((await self.web3.eth.get_block('latest'))['baseFeePerGas']))
            gas_price = await self._calculate_optimal_gas_price(base_fee)
            
            # Calculate potential profit
            profit = await self._calculate_potential_profit(
                frontrun_amount,
                swap_data,
                pool_data,
                gas_price
            )
            
            if profit < self.min_profit_wei:
                logger.debug(f"Insufficient profit: {profit} < {self.min_profit_wei}")
                return None
            
            return {
                'type': 'frontrun',
                'dex': swap_data['dex'],
                'token_in': swap_data['path'][0],
                'token_out': swap_data['path'][1],
                'target_amount': int(swap_data['amountIn']),
                'frontrun_amount': int(frontrun_amount),
                'pool_address': pool_data['pair_address'],
                'gas_price': int(gas_price),
                'expected_profit': int(profit),
                'competition_level': float(self._competition_level),
                'target_tx_hash': tx['hash'],
                'timestamp': int(time.time())
            }
            
        except Exception as e:
            logger.error(f"Error analyzing frontrun opportunity: {e}")
            return None

    async def execute_opportunity(self, opportunity: Dict) -> bool:
        """Execute frontrun opportunity using flash loans through Flashbots."""
        if not opportunity or opportunity['type'] != 'frontrun':
            return False
            
        try:
            # Prepare execution parameters
            execution_deadline = int(time.time() + 120)  # 2 minute deadline
            
            # Calculate total flash loan amount needed
            total_loan_amount = opportunity['frontrun_amount']
            
            # Encode the frontrun strategy callback for the flash loan
            callback_data = self._encode_strategy_callback(
                'frontrun',
                opportunity['token_in'],
                opportunity['token_out'],
                total_loan_amount,
                opportunity['pool_address'],
                target_tx_hash=opportunity['target_tx_hash']
            )
            
            # Execute the frontrun attack using flash loan through Flashbots
            success, profit = await self._execute_with_flash_loan(
                opportunity['token_in'],
                total_loan_amount,
                callback_data,
                opportunity['gas_price']
            )
            
            # Record result for competition monitoring
            self._recent_frontruns.append({
                'timestamp': time.time(),
                'success': success,
                'competition_level': float(self._competition_level)
            })
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing frontrun opportunity: {e}")
            return False

    async def _monitor_competition(self) -> None:
        """Monitor and adjust for MEV competition."""
        try:
            # Clean old entries
            current_time = time.time()
            self._recent_frontruns = [f for f in self._recent_frontruns 
                                    if current_time - f['timestamp'] < 300]  # Keep last 5 minutes
            
            if not self._recent_frontruns:
                self._competition_level = Decimal('1.0')
                return
            
            # Calculate success rate
            success_count = sum(1 for f in self._recent_frontruns if f['success'])
            total_count = len(self._recent_frontruns)
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

    async def _validate_frontrun_opportunity(
        self,
        victim_tx: Dict,
        pool_data: Dict,
        swap_data: Dict
    ) -> Tuple[bool, str]:
        """Validate frontrun opportunity with mainnet considerations."""
        try:
            # Check basic transaction validity
            if not all([victim_tx, pool_data, swap_data]):
                return False, "Missing required data"
            
            # Validate victim amount
            victim_amount = Decimal(str(swap_data['amountIn']))
            if victim_amount > self.max_position_size:
                return False, "Target transaction too large"
            
            # Calculate and validate price impact
            price_impact = self.dex_handler.calculate_price_impact(
                int(victim_amount),
                pool_data['reserves']['token0'],
                pool_data['reserves']['token1'],
                pool_data['fee']
            )
            
            if price_impact > self.max_price_impact:
                return False, f"Price impact too high: {price_impact}%"
            
            # Check pool liquidity
            total_liquidity = Decimal(str(pool_data['reserves']['token0'])) + Decimal(str(pool_data['reserves']['token1']))
            min_liquidity = victim_amount * Decimal('20')  # Require 20x victim amount in liquidity
            if total_liquidity < min_liquidity:
                return False, "Insufficient pool liquidity"
            
            # Validate gas price competitiveness
            victim_gas_price = Decimal(str(victim_tx.get('gasPrice', 0)))
            if victim_gas_price <= Decimal(str(self.base_priority_fee)):
                return False, "Target gas price too low"
            
            return True, "Valid frontrun opportunity"
            
        except Exception as e:
            logger.error(f"Error validating frontrun opportunity: {e}")
            return False, f"Validation error: {str(e)}"

    async def _calculate_optimal_amount(
        self,
        victim_amount: Decimal,
        reserve_in: Decimal,
        reserve_out: Decimal,
        fee: Decimal
    ) -> Decimal:
        """Calculate optimal frontrun amount."""
        try:
            # Calculate optimal frontrun amount (typically 50-150% of victim amount)
            base_amount = victim_amount * Decimal('0.5')  # Start with 50% of victim amount
            max_amount = min(
                victim_amount * Decimal('1.5'),  # Max 150% of victim amount
                reserve_in * Decimal('0.1')      # Max 10% of pool reserves
            )
            
            return min(base_amount, max_amount)
            
        except Exception as e:
            logger.error(f"Error calculating optimal amount: {e}")
            return Decimal('0')

    async def _calculate_potential_profit(
        self,
        frontrun_amount: Decimal,
        swap_data: Dict,
        pool_data: Dict,
        gas_price: Decimal
    ) -> Decimal:
        """Calculate potential profit with mainnet considerations."""
        try:
            # Calculate gas costs
            total_gas = self.base_gas * (Decimal('1') + self.gas_buffer_percent / Decimal('100'))
            total_gas_cost = total_gas * gas_price
            
            # Calculate expected output
            output_amount = await self._simulate_swap_output(
                frontrun_amount,
                Decimal(str(pool_data['reserves']['token0'])),
                Decimal(str(pool_data['reserves']['token1'])),
                pool_data['fee']
            )
            
            # Calculate net profit
            gross_profit = output_amount - frontrun_amount
            net_profit = gross_profit - total_gas_cost
            
            # Apply safety margin
            safety_margin = Decimal('0.9')  # 10% safety margin
            return net_profit * safety_margin
            
        except Exception as e:
            logger.error(f"Error calculating potential profit: {e}")
            return Decimal('0')

    async def _simulate_swap_output(
        self,
        amount_in: Decimal,
        reserve_in: Decimal,
        reserve_out: Decimal,
        fee: Decimal
    ) -> Decimal:
        """Simulate swap output with precise calculations."""
        try:
            # Calculate amount after fee
            amount_in_with_fee = amount_in * (Decimal('1') - fee)
            
            # Calculate constant product k
            k = reserve_in * reserve_out
            
            # Calculate new reserves after swap
            new_reserve_in = reserve_in + amount_in_with_fee
            new_reserve_out = k / new_reserve_in
            
            # Calculate output amount
            output_amount = reserve_out - new_reserve_out
            
            return output_amount
            
        except Exception as e:
            logger.error(f"Error simulating swap output: {e}")
            return Decimal('0')
