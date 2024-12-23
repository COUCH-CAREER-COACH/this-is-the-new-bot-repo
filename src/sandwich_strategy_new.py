"""Enhanced Sandwich Strategy Implementation."""
from typing import Dict, Optional, List, Tuple, Any
from decimal import Decimal
from web3 import Web3
import asyncio

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

class EnhancedSandwichStrategy(MEVStrategy):
    """Enhanced sandwich trading strategy with improved safety and efficiency."""
    
    def __init__(self, w3: Web3, config: Dict[str, Any]):
        """Initialize sandwich strategy."""
        super().__init__(w3, config)
        
        try:
            # Initialize DEX handler
            self.dex_handler = DEXHandler(w3, config)
            
            # Load sandwich-specific configuration
            sandwich_config = config.get('strategies', {}).get('sandwich', {})
            self.min_profit_wei = int(sandwich_config.get(
                'min_profit_wei',
                mainnet.MIN_PROFIT_THRESHOLD * 2  # Higher threshold for sandwich
            ))
            self.max_position_size = int(sandwich_config.get(
                'max_position_size',
                mainnet.MAX_POSITION_SIZE // 2  # Lower position size for safety
            ))
            self.max_blocks_to_wait = int(sandwich_config.get(
                'max_blocks_to_wait',
                1  # Must execute quickly
            ))
            self.min_victim_size = int(sandwich_config.get(
                'min_victim_size',
                self.web3.to_wei(0.5, 'ether')  # Minimum victim transaction size
            ))
            
            # Load contract ABIs
            self.token_abi = self._load_abi('contracts/interfaces/IERC20.json')
            self.pair_abi = self._load_abi('contracts/interfaces/IUniswapV2Pair.json')
            self.router_abi = self._load_abi('contracts/interfaces/IUniswapV2Router02.json')
            
            logger.info("Enhanced sandwich strategy initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing sandwich strategy: {e}")
            raise ConfigurationError(f"Failed to initialize sandwich strategy: {e}")

    async def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze transaction for sandwich opportunity."""
        if not tx or not isinstance(tx, dict):
            return None
            
        try:
            # Decode swap data
            swap_data = self.dex_handler.decode_swap_data(tx)
            if not swap_data:
                return None
                
            # Validate victim transaction size
            if swap_data['amount_in'] < self.min_victim_size:
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
                
            # Calculate optimal sandwich position
            frontrun_size, backrun_size, profit = await self._calculate_optimal_sandwich(
                pool_info,
                swap_data['amount_in'],
                swap_data['path'][0],
                swap_data['path'][1]
            )
            
            if not frontrun_size or not backrun_size or profit < self.min_profit_wei:
                return None
                
            # Calculate gas costs
            needs_approvals = not (
                await token_checks.check_token_allowance(
                    self.web3,
                    swap_data['path'][0],
                    self.token_abi,
                    self.account.address,
                    [pool_info['pair_address']],
                    frontrun_size
                )
            )
            
            gas_estimate = mainnet.calculate_gas_estimate(needs_approvals) * 2  # Two transactions
            gas_price = await self.web3.eth.gas_price
            
            if not mainnet.validate_gas_price(gas_price):
                return None
                
            # Create opportunity
            opportunity = {
                'type': 'sandwich',
                'token_in': swap_data['path'][0],
                'token_out': swap_data['path'][1],
                'frontrun_amount': frontrun_size,
                'backrun_amount': backrun_size,
                'profit': profit,
                'gas_price': gas_price,
                'gas_estimate': gas_estimate,
                'pool': pool_info['pair_address'],
                'victim_tx': tx['hash'],
                'deadline': swap_data['deadline'],
                'timestamp': self.web3.eth.get_block('latest').timestamp
            }
            
            return opportunity
            
        except Exception as e:
            logger.error(f"Error analyzing sandwich opportunity: {e}")
            return None

    async def execute_opportunity(self, opportunity: Dict) -> bool:
        """Execute sandwich opportunity."""
        try:
            # Validate execution conditions
            conditions_valid = await self._validate_execution_conditions(opportunity)
            if not conditions_valid:
                return False
                
            # Execute frontrun transaction
            frontrun_success = await self._execute_frontrun(opportunity)
            if not frontrun_success:
                return False
                
            # Monitor victim transaction
            victim_included = await self._monitor_victim_transaction(
                opportunity['victim_tx'],
                opportunity['deadline']
            )
            if not victim_included:
                return False
                
            # Execute backrun transaction
            backrun_success = await self._execute_backrun(opportunity)
            
            return backrun_success
            
        except Exception as e:
            logger.error(f"Error executing sandwich opportunity: {e}")
            return False

    async def _calculate_optimal_sandwich(
        self,
        pool_info: Dict,
        victim_amount: int,
        token_in: str,
        token_out: str
    ) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """Calculate optimal sandwich position sizes."""
        try:
            # Get current reserves
            reserves = pool_info['reserves']
            
            # Calculate optimal frontrun size using binary search
            min_amount = self.web3.to_wei(0.1, 'ether')  # 0.1 ETH minimum
            max_amount = min(
                int(reserves['token0'] * Decimal('0.1')),  # 10% of pool liquidity
                self.max_position_size
            )
            
            optimal_frontrun = None
            optimal_backrun = None
            max_profit = 0
            
            while min_amount <= max_amount:
                frontrun_amount = (min_amount + max_amount) // 2
                
                # Calculate expected profit
                try:
                    backrun_amount, profit = await self._calculate_sandwich_profit(
                        frontrun_amount,
                        victim_amount,
                        reserves['token0'],
                        reserves['token1']
                    )
                    
                    if profit > max_profit:
                        max_profit = profit
                        optimal_frontrun = frontrun_amount
                        optimal_backrun = backrun_amount
                        min_amount = frontrun_amount + 1  # Try larger amounts
                    else:
                        max_amount = frontrun_amount - 1  # Try smaller amounts
                        
                except (InsufficientLiquidityError, ExcessiveSlippageError):
                    max_amount = frontrun_amount - 1
                    
            return optimal_frontrun, optimal_backrun, max_profit
            
        except Exception as e:
            logger.error(f"Error calculating optimal sandwich: {e}")
            return None, None, None

    async def _calculate_sandwich_profit(
        self,
        frontrun_amount: int,
        victim_amount: int,
        reserve0: int,
        reserve1: int
    ) -> Tuple[int, int]:
        """Calculate expected profit from sandwich attack."""
        try:
            # Calculate state after frontrun
            amount_in_with_fee = int(frontrun_amount * 997)  # 0.3% fee
            new_reserve0 = reserve0 + amount_in_with_fee
            frontrun_out = (amount_in_with_fee * reserve1) // (reserve0 * 1000 + amount_in_with_fee)
            new_reserve1 = reserve1 - frontrun_out
            
            # Calculate victim's output
            victim_in_with_fee = int(victim_amount * 997)
            victim_out = (victim_in_with_fee * new_reserve1) // (new_reserve0 * 1000 + victim_in_with_fee)
            
            # Calculate state after victim
            final_reserve0 = new_reserve0 + victim_in_with_fee
            final_reserve1 = new_reserve1 - victim_out
            
            # Calculate optimal backrun
            backrun_amount = frontrun_out + victim_out
            backrun_in_with_fee = int(backrun_amount * 997)
            backrun_out = (backrun_in_with_fee * final_reserve0) // (final_reserve1 * 1000 + backrun_in_with_fee)
            
            # Calculate profit
            profit = backrun_out - frontrun_amount
            
            if profit <= 0:
                raise InsufficientLiquidityError("No profit opportunity")
                
            return backrun_amount, profit
            
        except Exception as e:
            logger.error(f"Error calculating sandwich profit: {e}")
            raise

    async def _validate_execution_conditions(self, opportunity: Dict) -> bool:
        """Validate conditions before executing sandwich attack."""
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

    async def _execute_frontrun(self, opportunity: Dict) -> bool:
        """Execute frontrun transaction."""
        try:
            # Get router contract
            router_contract = self.web3.eth.contract(
                address=self.config['dex']['uniswap_v2_router'],
                abi=self.router_abi
            )
            
            # Build transaction
            deadline = opportunity['deadline']
            path = [opportunity['token_in'], opportunity['token_out']]
            
            tx = await router_contract.functions.swapExactTokensForTokens(
                opportunity['frontrun_amount'],
                0,  # Accept any amount of tokens
                path,
                self.account.address,
                deadline
            ).build_transaction({
                'from': self.account.address,
                'gas': opportunity['gas_estimate'] // 2,
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
            logger.error(f"Error executing frontrun: {e}")
            return False

    async def _execute_backrun(self, opportunity: Dict) -> bool:
        """Execute backrun transaction."""
        try:
            # Get router contract
            router_contract = self.web3.eth.contract(
                address=self.config['dex']['uniswap_v2_router'],
                abi=self.router_abi
            )
            
            # Build transaction
            deadline = opportunity['deadline']
            path = [opportunity['token_out'], opportunity['token_in']]
            
            tx = await router_contract.functions.swapExactTokensForTokens(
                opportunity['backrun_amount'],
                0,  # Accept any amount of tokens
                path,
                self.account.address,
                deadline
            ).build_transaction({
                'from': self.account.address,
                'gas': opportunity['gas_estimate'] // 2,
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
            logger.error(f"Error executing backrun: {e}")
            return False

    async def _monitor_victim_transaction(
        self,
        victim_tx: str,
        deadline: int
    ) -> bool:
        """Monitor victim transaction inclusion."""
        try:
            start_block = self.web3.eth.block_number
            
            while self.web3.eth.block_number <= start_block + self.max_blocks_to_wait:
                try:
                    receipt = await self.web3.eth.get_transaction_receipt(victim_tx)
                    if receipt:
                        return receipt['status'] == 1
                except Exception:
                    pass
                    
                if self.web3.eth.get_block('latest').timestamp >= deadline:
                    return False
                    
                await asyncio.sleep(0.1)  # Quick polling
                
            return False
            
        except Exception as e:
            logger.error(f"Error monitoring victim transaction: {e}")
            return False
