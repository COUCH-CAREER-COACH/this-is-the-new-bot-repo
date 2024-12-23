from decimal import Decimal
import logging
from .custom_exceptions import (
    GasEstimationError,
    ContractLogicError,
    ContractError,
    GasPriceError,
    ProfitabilityError,
    ConfigurationError,
    InsufficientLiquidityError,
    ExcessiveSlippageError
)

# Initialize logger
logger = logging.getLogger(__name__)

# Define constants
MAX_GAS_PRICE = 100 * 10**9  # Example value in GWEI
MIN_PROFIT_THRESHOLD = 0.01 * 10**18  # Example value in ETH

async def calculate_gas_cost(estimated_gas, gas_price, profit, min_profit_multiplier, required_profit):
    # Calculate gas cost with current network conditions
    try:
        base_cost = estimated_gas * gas_price

        # Add priority fee for faster inclusion
        priority_fee = await web3.eth.max_priority_fee_per_gas  # Removed self
        priority_cost = estimated_gas * priority_fee

        # Total gas cost with safety buffer
        gas_cost = int((base_cost + priority_cost) * Decimal('1.2'))

        # Calculate net profit
        net_profit = profit - gas_cost

        # Log detailed analysis
        logger.debug(f"Network conditions:")
        logger.debug(f"  Base gas price: {gas_price / 10**9:.2f} GWEI")
        logger.debug(f"  Priority fee: {priority_fee / 10**9:.2f} GWEI")
        logger.debug(f"  Estimated gas: {estimated_gas}")
        logger.debug(f"Costs:")
        logger.debug(f"  Base cost: {base_cost / 10**18:.4f} ETH")
        logger.debug(f"  Priority cost: {priority_cost / 10**18:.4f} ETH")
        logger.debug(f"  Total gas cost: {gas_cost / 10**18:.4f} ETH")
        logger.debug(f"Profitability:")
        logger.debug(f"  Required multiplier: {min_profit_multiplier:.2f}x")
        logger.debug(f"  Required profit: {required_profit / 10**18:.4f} ETH")
        logger.debug(f"  Gross profit: {profit / 10**18:.4f} ETH")
        logger.debug(f"  Net profit: {net_profit / 10**18:.4f} ETH")

    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating gas costs: {e}")
        raise GasEstimationError(f"Failed to estimate gas costs: {e}")
    except ContractLogicError as e:
        logger.error(f"Contract error during gas estimation: {e}")
        raise ContractError(f"Contract error during gas estimation: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during gas estimation: {e}")
        raise GasEstimationError(f"Unexpected error during gas estimation: {e}")

    try:
        # Get current network conditions
        base_fee = await web3.eth.get_block('latest')
        base_fee = base_fee.get('baseFeePerGas', web3.eth.gas_price)
        priority_fee = await web3.eth.max_priority_fee_per_gas

        # Calculate effective gas price with current network conditions
        effective_gas_price = base_fee + priority_fee
        if effective_gas_price > MAX_GAS_PRICE:
            raise GasPriceError(f"Gas price too high: {effective_gas_price / 10**9:.2f} GWEI")

        # Calculate gas costs including all operations
        base_cost = estimated_gas * base_fee
        priority_cost = estimated_gas * priority_fee
        total_cost = base_cost + priority_cost

        # Add safety buffer for mainnet conditions
        gas_cost = int(total_cost * Decimal('1.2'))

        # Calculate and validate net profit
        net_profit = profit - gas_cost
        if net_profit < MIN_PROFIT_THRESHOLD:
            raise ProfitabilityError(
                f"Insufficient profit after gas: {net_profit / 10**18:.4f} ETH"
            )

        # Calculate and validate profit ratio
        profit_ratio = Decimal(str(net_profit)) / Decimal(str(gas_cost))
        if profit_ratio < Decimal('2'):
            raise ProfitabilityError(
                f"Profit/gas ratio too low: {profit_ratio:.2f}x"
            )

        # Log detailed analysis for monitoring
        logger.debug("Network Conditions:")
        logger.debug(f"  Base fee: {base_fee / 10**9:.2f} GWEI")
        logger.debug(f"  Priority fee: {priority_fee / 10**9:.2f} GWEI")
        logger.debug(f"  Effective gas price: {effective_gas_price / 10**9:.2f} GWEI")
        logger.debug("Gas Costs:")
        logger.debug(f"  Estimated gas units: {estimated_gas:,}")
        logger.debug(f"  Base cost: {base_cost / 10**18:.4f} ETH")
        logger.debug(f"  Priority cost: {priority_cost / 10**18:.4f} ETH")
        logger.debug(f"  Total cost with buffer: {gas_cost / 10**18:.4f} ETH")
        logger.debug("Profitability:")
        logger.debug(f"  Gross profit: {profit / 10**18:.4f} ETH")
        logger.debug(f"  Net profit: {net_profit / 10**18:.4f} ETH")
        logger.debug(f"  Profit ratio: {profit_ratio:.2f}x")

        return gas_cost, net_profit

    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating gas costs: {e}")
        raise GasEstimationError(f"Failed to estimate gas costs: {e}")
    except ContractLogicError as e:
        logger.error(f"Contract error during gas estimation: {e}")
        raise ContractError(f"Contract error during gas estimation: {e}")
    except (GasPriceError, ProfitabilityError) as e:
        logger.debug(str(e))
        return None
    except Exception as e:
        logger.error(f"Unexpected error during gas estimation: {e}")
        raise GasEstimationError(f"Unexpected error during gas estimation: {e}")
