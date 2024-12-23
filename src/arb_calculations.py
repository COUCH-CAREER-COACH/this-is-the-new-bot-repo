"""Arbitrage calculations and optimization module."""
from typing import Dict, Tuple, Optional, TYPE_CHECKING
from decimal import Decimal
import asyncio
from web3 import Web3

from .logger_config import logger
from .exceptions import (
    CalculationError,
    InsufficientLiquidityError,
    ExcessiveSlippageError
)
from . import mainnet_helpers as mainnet

if TYPE_CHECKING:
    from .arbitrage_strategy_v2 import EnhancedArbitrageStrategy

async def calculate_optimal_arbitrage(
    strategy: 'EnhancedArbitrageStrategy',
    pool_data_uni: Dict,
    pool_data_sushi: Dict,
    token_in: str,
    token_out: str
) -> Tuple[Optional[int], Optional[int]]:
    """Calculate optimal arbitrage amount and expected profit."""
    try:
        # Validate inputs
        if not await mainnet.validate_token_pair(strategy.web3, token_in, token_out):
            return None, None
            
        # Get pool reserves
        uni_reserves = pool_data_uni['reserves']
        sushi_reserves = pool_data_sushi['reserves']
        
        # Calculate optimal amount using binary search
        min_amount = strategy.web3.to_wei(0.1, 'ether')  # 0.1 ETH minimum
        max_amount = min(
            int(uni_reserves['token0'] * Decimal('0.1')),  # 10% of pool liquidity
            int(sushi_reserves['token0'] * Decimal('0.1')),
            strategy.max_position_size
        )
        
        optimal_amount = None
        max_profit = 0
        
        # Binary search for optimal amount
        while min_amount <= max_amount:
            amount = (min_amount + max_amount) // 2
            
            # Calculate amounts through both paths
            try:
                # Uniswap path
                uni_out = await calculate_out_amount(
                    strategy.web3,
                    amount,
                    uni_reserves['token0'],
                    uni_reserves['token1'],
                    strategy.max_slippage
                )
                
                # Sushiswap path
                sushi_out = await calculate_out_amount(
                    strategy.web3,
                    uni_out,
                    sushi_reserves['token1'],
                    sushi_reserves['token0'],
                    strategy.max_slippage
                )
                
                # Calculate profit
                profit = sushi_out - amount
                
                # Check if this is more profitable
                if profit > max_profit:
                    max_profit = profit
                    optimal_amount = amount
                    
                # Adjust search range
                if sushi_out > amount:
                    min_amount = amount + 1  # Try larger amounts
                else:
                    max_amount = amount - 1  # Try smaller amounts
                    
            except (InsufficientLiquidityError, ExcessiveSlippageError):
                max_amount = amount - 1  # Reduce amount if error
                
        # Validate results
        if optimal_amount and max_profit > 0:
            # Calculate gas costs
            gas_price = await strategy.web3.eth.gas_price
            gas_cost = mainnet.calculate_gas_estimate(True) * gas_price
            
            # Verify profitability after gas
            is_profitable, net_profit = await mainnet.estimate_arbitrage_profit(
                optimal_amount,
                optimal_amount + max_profit,
                gas_price,
                mainnet.calculate_gas_estimate(True)
            )
            
            if is_profitable:
                logger.info(f"Found profitable arbitrage: {net_profit} wei profit")
                return optimal_amount, net_profit
                
        return None, None
        
    except Exception as e:
        logger.error(f"Error calculating optimal arbitrage: {e}")
        raise CalculationError(f"Failed to calculate optimal arbitrage: {e}")

async def calculate_out_amount(
    w3: Web3,
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
    max_slippage: Decimal
) -> int:
    """Calculate output amount for a swap."""
    try:
        # Validate inputs
        if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
            raise ValueError("Invalid input amounts or reserves")
            
        # Calculate price impact
        price_impact = mainnet.calculate_price_impact(
            amount_in,
            reserve_in,
            reserve_out
        )
        
        # Check if price impact exceeds slippage tolerance
        if price_impact > max_slippage * 100:  # Convert max_slippage to percentage
            raise ExcessiveSlippageError(
                f"Price impact {price_impact}% exceeds maximum slippage {max_slippage * 100}%"
            )
            
        # Calculate output amount using constant product formula
        # (x + Δx)(y - Δy) = xy
        # Solving for Δy:
        # Δy = (y * Δx) / (x + Δx)
        amount_in_with_fee = int(amount_in * 997)  # 0.3% fee
        numerator = amount_in_with_fee * reserve_out
        denominator = (reserve_in * 1000) + amount_in_with_fee
        amount_out = numerator // denominator
        
        # Validate output amount
        if amount_out <= 0:
            raise InsufficientLiquidityError("Calculated output amount is zero or negative")
            
        if amount_out >= reserve_out:
            raise InsufficientLiquidityError("Output amount exceeds available liquidity")
            
        return amount_out
        
    except Exception as e:
        logger.error(f"Error calculating output amount: {e}")
        raise CalculationError(f"Failed to calculate output amount: {e}")

async def validate_arbitrage_path(
    strategy: 'EnhancedArbitrageStrategy',
    token_in: str,
    token_out: str,
    amount: int,
    uni_pool: str,
    sushi_pool: str
) -> bool:
    """Validate complete arbitrage path."""
    try:
        # Validate token addresses
        if not await mainnet.validate_token_pair(strategy.web3, token_in, token_out):
            return False
            
        # Validate pool addresses
        if not mainnet.is_contract(strategy.web3, uni_pool) or \
           not mainnet.is_contract(strategy.web3, sushi_pool):
            return False
            
        # Validate amount
        if amount <= 0 or amount > strategy.max_position_size:
            return False
            
        # Check pool liquidity
        if not await strategy.validate_pool_liquidity(token_in, token_out, amount):
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error validating arbitrage path: {e}")
        return False

async def simulate_arbitrage(
    strategy: 'EnhancedArbitrageStrategy',
    token_in: str,
    token_out: str,
    amount: int,
    uni_pool: str,
    sushi_pool: str
) -> Tuple[bool, int]:
    """Simulate arbitrage execution."""
    try:
        # Validate path first
        if not await validate_arbitrage_path(
            strategy,
            token_in,
            token_out,
            amount,
            uni_pool,
            sushi_pool
        ):
            return False, 0
            
        # Get pool data
        pool_data_uni = await strategy.dex_handler.get_pool_info(
            'uniswap',
            token_in,
            token_out
        )
        pool_data_sushi = await strategy.dex_handler.get_pool_info(
            'sushiswap',
            token_in,
            token_out
        )
        
        # Calculate expected outputs
        amount_out_uni = await calculate_out_amount(
            strategy.web3,
            amount,
            pool_data_uni['reserves']['token0'],
            pool_data_uni['reserves']['token1'],
            strategy.max_slippage
        )
        
        amount_out_sushi = await calculate_out_amount(
            strategy.web3,
            amount_out_uni,
            pool_data_sushi['reserves']['token1'],
            pool_data_sushi['reserves']['token0'],
            strategy.max_slippage
        )
        
        # Calculate profit
        profit = amount_out_sushi - amount
        
        # Estimate gas costs
        gas_price = await strategy.web3.eth.gas_price
        gas_estimate = mainnet.calculate_gas_estimate(True)
        gas_cost = gas_price * gas_estimate
        
        # Calculate net profit
        net_profit = profit - gas_cost
        
        # Validate profitability
        is_profitable = net_profit > strategy.min_profit_wei
        
        return is_profitable, net_profit
        
    except Exception as e:
        logger.error(f"Error simulating arbitrage: {e}")
        return False, 0
