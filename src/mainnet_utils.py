"""Mainnet-specific utilities and constants for arbitrage bot."""
from decimal import Decimal
from web3.types import Wei

# Network constants
MAINNET_CHAIN_ID = 1
BASE_GAS_PRICE = 30 * 10**9  # 30 GWEI
MAX_GAS_PRICE = 500 * 10**9  # 500 GWEI
MIN_GAS_BUFFER = 10  # 10%

# Pool size thresholds
MIN_ETH_LIQUIDITY = Wei(50 * 10**18)  # 50 ETH minimum pool size
MIN_USDC_LIQUIDITY = 1_000_000 * 10**6  # $1M USDC minimum

# Position limits
MAX_POSITION_SIZE = Wei(100 * 10**18)  # 100 ETH
MAX_POOL_USAGE = Decimal('0.03')  # Max 3% of pool size

# Profitability thresholds
MIN_PROFIT_THRESHOLD = Wei(0.01 * 10**18)  # 0.01 ETH
MIN_PROFIT_RATIO = Decimal('2')  # 2x minimum return on gas
MIN_PRICE_DIFFERENCE = Decimal('0.01')  # 1% minimum price difference

# Safety parameters
MAX_PRICE_IMPACT = Decimal('0.005')  # 0.5% max price impact
MAX_SLIPPAGE = Decimal('0.02')  # 2% max slippage
MAX_PRICE_DEVIATION = Decimal('0.1')  # 10% max price deviation between pools
MAX_RESERVE_RATIO_DEVIATION = Decimal('0.2')  # 20% max reserve ratio deviation

# Gas estimates
BASE_TX_GAS = 21000
FLASH_LOAN_BORROW_GAS = 300000
FLASH_LOAN_REPAY_GAS = 200000
DEX_SWAP_GAS = 150000
TOKEN_APPROVAL_GAS = 50000
SAFETY_MARGIN_GAS = 100000

# Time thresholds
MAX_DATA_AGE = 300  # 5 minutes maximum data age
BLOCK_TIME_BUFFER = 2  # 2 blocks buffer for execution

def calculate_gas_estimate(needs_approvals: bool = False) -> int:
    """Calculate total gas estimate for arbitrage transaction."""
    total_gas = (
        BASE_TX_GAS +
        FLASH_LOAN_BORROW_GAS +
        FLASH_LOAN_REPAY_GAS +
        (2 * DEX_SWAP_GAS) +  # Two swaps
        SAFETY_MARGIN_GAS
    )
    
    if needs_approvals:
        total_gas += (2 * TOKEN_APPROVAL_GAS)  # Two token approvals
        
    return total_gas

def validate_pool_size(eth_balance: int, usdc_balance: int) -> bool:
    """Validate pool has sufficient liquidity."""
    return (
        eth_balance >= MIN_ETH_LIQUIDITY and
        usdc_balance >= MIN_USDC_LIQUIDITY
    )

def calculate_price_impact(
    amount: Decimal,
    reserve: Decimal,
    decimals: int = 18
) -> Decimal:
    """Calculate price impact of trade."""
    normalized_amount = amount / Decimal(10**decimals)
    normalized_reserve = reserve / Decimal(10**decimals)
    return (normalized_amount / normalized_reserve) * Decimal('100')

def is_profitable_after_gas(
    profit: int,
    gas_cost: int,
    gas_price: int
) -> bool:
    """Check if trade is profitable after gas costs."""
    net_profit = profit - gas_cost
    if net_profit < MIN_PROFIT_THRESHOLD:
        return False
        
    profit_ratio = Decimal(str(net_profit)) / Decimal(str(gas_cost))
    if profit_ratio < MIN_PROFIT_RATIO:
        return False
        
    return True
