"""Mainnet validation utilities for arbitrage bot."""
from decimal import Decimal
import time
import logging
from typing import Dict

logger = logging.getLogger('arbitrage-bot')

def validate_price_deviation(
    price1: Decimal,
    price2: Decimal,
    max_deviation: Decimal
) -> bool:
    """Validate price deviation between two pools."""
    avg_price = (price1 + price2) / Decimal('2')
    if avg_price == 0:
        return False
    deviation1 = abs(price1 - avg_price) / avg_price
    deviation2 = abs(price2 - avg_price) / avg_price
    return deviation1 <= max_deviation and deviation2 <= max_deviation

def validate_reserve_ratio(
    ratio1: Decimal,
    ratio2: Decimal,
    max_deviation: Decimal
) -> bool:
    """Validate reserve ratio deviation between two pools."""
    min_ratio = min(ratio1, ratio2)
    if min_ratio == 0:
        return False
    deviation = abs(ratio1 - ratio2) / min_ratio
    return deviation <= max_deviation

def validate_data_age(timestamp: int, max_age: int) -> bool:
    """Validate data is not too old."""
    current_time = int(time.time())
    return (current_time - timestamp) <= max_age

def calculate_required_profit(
    base_profit: int,
    gas_price: int,
    base_gas_price: int
) -> int:
    """Calculate required profit based on gas price scaling."""
    gas_multiplier = Decimal(str(gas_price)) / Decimal(str(base_gas_price))
    # Exponential scaling for high gas prices
    profit_multiplier = gas_multiplier ** Decimal('1.5')
    return int(Decimal(str(base_profit)) * profit_multiplier)

def validate_pool_data(pool_data: Dict) -> bool:
    """Validate pool data has all required fields."""
    required_fields = {'reserves', 'fee', 'pair_address'}
    reserve_fields = {'token0', 'token1'}
    
    if not all(field in pool_data for field in required_fields):
        return False
        
    if not all(field in pool_data['reserves'] for field in reserve_fields):
        return False
        
    return True

def calculate_gas_with_priority(
    estimated_gas: int,
    base_fee: int,
    priority_fee: int,
    buffer_percent: int = 20
) -> int:
    """Calculate total gas cost including priority fee and safety buffer."""
    base_cost = estimated_gas * base_fee
    priority_cost = estimated_gas * priority_fee
    total_cost = base_cost + priority_cost
    
    # Add safety buffer
    buffer_multiplier = Decimal(str(100 + buffer_percent)) / Decimal('100')
    return int(Decimal(str(total_cost)) * buffer_multiplier)

def validate_gas_price(
    gas_price: int,
    max_gas_price: int
) -> bool:
    """Validate gas price is within acceptable range."""
    return gas_price <= max_gas_price

def validate_price_impact(
    amount: Decimal,
    reserve: Decimal,
    max_impact: Decimal,
    decimals: int = 18
) -> bool:
    """Validate price impact is within acceptable range."""
    normalized_amount = amount / Decimal(10**decimals)
    normalized_reserve = reserve / Decimal(10**decimals)
    impact = (normalized_amount / normalized_reserve) * Decimal('100')
    return impact <= max_impact
