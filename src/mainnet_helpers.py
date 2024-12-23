"""Helper functions for mainnet operations."""
from typing import Dict, Optional, List, Tuple, Any
from decimal import Decimal
from web3 import Web3
import time
import asyncio

from .logger_config import logger
from .exceptions import (
    ValidationError,
    NetworkError,
    SecurityError
)

# Mainnet Constants
MAINNET_CHAIN_ID = 1
MIN_PROFIT_THRESHOLD = 50000000000000000  # 0.05 ETH
MAX_POSITION_SIZE = 1000000000000000000000  # 1000 ETH
MAX_GAS_PRICE = 500000000000  # 500 GWEI
MIN_LIQUIDITY = 1000000000000000000  # 1 ETH
MAX_SLIPPAGE = Decimal('0.03')  # 3%
BLOCK_TIME = 12  # seconds

async def validate_network(w3: Web3) -> bool:
    """Validate connection to mainnet."""
    try:
        chain_id = await w3.eth.chain_id
        if chain_id != MAINNET_CHAIN_ID:
            raise NetworkError(f"Not connected to mainnet. Chain ID: {chain_id}")
            
        # Check sync status
        sync_status = await w3.eth.syncing
        if sync_status:
            raise NetworkError("Node is still syncing")
            
        # Check block delay
        latest_block = await w3.eth.get_block('latest')
        block_delay = int(time.time()) - latest_block['timestamp']
        if block_delay > BLOCK_TIME * 2:
            raise NetworkError(f"Node is behind by {block_delay} seconds")
            
        return True
        
    except Exception as e:
        logger.error(f"Network validation failed: {e}")
        return False

def validate_gas_price(gas_price: int) -> bool:
    """Validate gas price is within acceptable range."""
    try:
        if gas_price <= 0:
            return False
            
        if gas_price > MAX_GAS_PRICE:
            logger.warning(f"Gas price {gas_price} exceeds maximum {MAX_GAS_PRICE}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Gas price validation failed: {e}")
        return False

def validate_pool_data(pool_data: Dict) -> bool:
    """Validate pool data meets minimum requirements."""
    try:
        if not pool_data or not isinstance(pool_data, dict):
            return False
            
        # Check reserves
        reserves = pool_data.get('reserves', {})
        if not reserves.get('token0') or not reserves.get('token1'):
            return False
            
        # Check minimum liquidity
        if reserves['token0'] < MIN_LIQUIDITY or reserves['token1'] < MIN_LIQUIDITY:
            return False
            
        # Check last update time
        if 'last_update' in pool_data:
            time_since_update = int(time.time()) - pool_data['last_update']
            if time_since_update > BLOCK_TIME * 3:  # More than 3 blocks old
                return False
                
        return True
        
    except Exception as e:
        logger.error(f"Pool data validation failed: {e}")
        return False

def calculate_gas_estimate(needs_approvals: bool = False) -> int:
    """Calculate gas estimate for transaction."""
    try:
        # Base gas costs
        base_gas = 21000  # ETH transfer base cost
        
        if needs_approvals:
            base_gas += 46000  # Approximate gas for ERC20 approve
            
        # Add buffer for mainnet
        gas_buffer = 50000  # Additional safety buffer
        
        return base_gas + gas_buffer
        
    except Exception as e:
        logger.error(f"Gas estimation failed: {e}")
        return 300000  # Conservative fallback

async def validate_transaction_data(
    w3: Web3,
    tx_data: Dict,
    max_value: int = MAX_POSITION_SIZE
) -> bool:
    """Validate transaction data for security."""
    try:
        # Check basic transaction requirements
        required_fields = ['to', 'value', 'data']
        if not all(field in tx_data for field in required_fields):
            return False
            
        # Validate addresses
        if not w3.is_address(tx_data['to']):
            return False
            
        # Check value limits
        if int(tx_data['value']) > max_value:
            return False
            
        # Validate gas price if present
        if 'gasPrice' in tx_data and not validate_gas_price(tx_data['gasPrice']):
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Transaction validation failed: {e}")
        return False

async def estimate_arbitrage_profit(
    amount_in: int,
    amount_out: int,
    gas_price: int,
    gas_used: int
) -> Tuple[bool, int]:
    """Estimate potential arbitrage profit."""
    try:
        # Calculate gas cost
        gas_cost = gas_price * gas_used
        
        # Calculate gross profit
        gross_profit = amount_out - amount_in
        
        # Calculate net profit
        net_profit = gross_profit - gas_cost
        
        # Apply safety margin for mainnet
        safety_margin = Decimal('0.9')  # 10% safety margin
        safe_profit = int(Decimal(str(net_profit)) * safety_margin)
        
        # Check against minimum threshold
        is_profitable = safe_profit > MIN_PROFIT_THRESHOLD
        
        return is_profitable, safe_profit
        
    except Exception as e:
        logger.error(f"Profit estimation failed: {e}")
        return False, 0

async def monitor_mempool(
    w3: Web3,
    target_addresses: List[str],
    callback: Any
) -> None:
    """Monitor mempool for specific addresses."""
    try:
        def handle_pending(tx_hash):
            try:
                # Get transaction
                tx = w3.eth.get_transaction(tx_hash)
                if not tx:
                    return
                    
                # Check if transaction is relevant
                if tx['to'] and tx['to'].lower() in [addr.lower() for addr in target_addresses]:
                    asyncio.create_task(callback(tx))
                    
            except Exception as e:
                logger.error(f"Error handling pending transaction: {e}")

        # Subscribe to pending transactions
        pending_filter = w3.eth.filter('pending')
        pending_filter.watch(handle_pending)
        
        # Keep the monitoring running
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Mempool monitoring failed: {e}")
        raise NetworkError(f"Failed to monitor mempool: {str(e)}")

async def validate_token_pair(
    w3: Web3,
    token0: str,
    token1: str
) -> bool:
    """Validate token pair for trading."""
    try:
        # Validate addresses
        if not w3.is_address(token0) or not w3.is_address(token1):
            return False
            
        # Check if addresses are different
        if token0.lower() == token1.lower():
            return False
            
        # Additional token validations could be added here
        # - Check if tokens are verified
        # - Check token implementation (ERC20 compliance)
        # - Check token liquidity
        # - Check token trading history
        
        return True
        
    except Exception as e:
        logger.error(f"Token pair validation failed: {e}")
        return False

def calculate_price_impact(
    amount: int,
    reserve_in: int,
    reserve_out: int
) -> Decimal:
    """Calculate price impact of a trade."""
    try:
        amount_decimal = Decimal(str(amount))
        reserve_in_decimal = Decimal(str(reserve_in))
        reserve_out_decimal = Decimal(str(reserve_out))
        
        # Calculate price impact
        price_impact = (amount_decimal / (reserve_in_decimal + amount_decimal)) * Decimal('100')
        
        return price_impact
        
    except Exception as e:
        logger.error(f"Price impact calculation failed: {e}")
        return Decimal('100')  # Return 100% impact on error

async def validate_slippage(
    expected_out: int,
    actual_out: int,
    max_slippage: Decimal = MAX_SLIPPAGE
) -> bool:
    """Validate transaction slippage."""
    try:
        if expected_out <= 0 or actual_out <= 0:
            return False
            
        # Calculate slippage
        slippage = (Decimal(str(expected_out)) - Decimal(str(actual_out))) / Decimal(str(expected_out))
        
        # Compare with maximum allowed slippage
        return slippage <= max_slippage
        
    except Exception as e:
        logger.error(f"Slippage validation failed: {e}")
        return False

def is_contract(w3: Web3, address: str) -> bool:
    """Check if address is a contract."""
    try:
        code = w3.eth.get_code(address)
        return code != b'' and code != '0x'
    except Exception as e:
        logger.error(f"Contract check failed: {e}")
        return False

async def validate_flashloan_params(
    token: str,
    amount: int,
    callback_data: bytes
) -> bool:
    """Validate flash loan parameters."""
    try:
        if not token or amount <= 0 or not callback_data:
            return False
            
        # Check amount against maximum position size
        if amount > MAX_POSITION_SIZE:
            return False
            
        # Validate callback data length
        if len(callback_data) < 4:  # At least function selector
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Flash loan parameter validation failed: {e}")
        return False
