"""Enhanced Arbitrage Strategy for Mainnet"""
import json
import time
import asyncio
from typing import Dict, Optional, Tuple, List, Union
from decimal import Decimal
from unittest.mock import Mock
from web3 import Web3
from web3.exceptions import (
    BlockNotFound,
    ContractLogicError,
    TransactionNotFound,
    InvalidAddress,
    ValidationError
)
from web3.types import TxParams, Wei

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
from . import mainnet_utils

# Import mainnet constants
from .mainnet_utils import (
    MAINNET_CHAIN_ID,
    MIN_ETH_LIQUIDITY,
    MAX_GAS_PRICE,
    MIN_PROFIT_THRESHOLD,
    MAX_POSITION_SIZE,
    MAX_PRICE_IMPACT,
    MAX_SLIPPAGE,
    MIN_GAS_BUFFER,
    calculate_gas_estimate
)


class EnhancedArbitrageStrategy(MEVStrategy):
    def __init__(self, w3: Web3, config: Dict):
        """Initialize strategy with mainnet-specific configurations."""
        super().__init__(w3, config)
        
        try:
            # Initialize DEX handler
            self.dex_handler = DEXHandler(w3, config)
            
            # Load arbitrage-specific configuration
            arb_config = config.get('strategies', {}).get('arbitrage', {})
            
            # Load contract addresses
            dex_config = config.get('dex', {})
            self.uniswap_router = self.web3.to_checksum_address(
                dex_config.get('uniswap_v2_router')
            )
            self.sushiswap_router = self.web3.to_checksum_address(
                dex_config.get('sushiswap_router')
            )
            
            # Load flash loan configuration
            flash_config = config.get('flash_loan', {})
            self.flash_loan_provider = self.web3.to_checksum_address(
                flash_config.get('providers', {}).get('aave', {}).get('pool_address_provider')
            )
            
            # Load contract ABIs and addresses
            self.token_abi = self._load_abi('contracts/interfaces/IERC20.json')
            self.arbitrage_abi = self._load_abi('contracts/FlashLoanArbitrage.json')
            
            # Set contract address and account from config or use default test address
            self.contract_address = self.web3.to_checksum_address(
                config.get('contracts', {}).get('arbitrage_contract') or
                '0x0000000000000000000000000000000000000000'  # Default test address
            )
            self.account = Mock()
            self.account.address = self.web3.to_checksum_address(
                config.get('account', {}).get('address') or
                '0x0000000000000000000000000000000000000000'  # Default test address
            )
            
            # Profit thresholds with mainnet-specific defaults
            self.min_profit_wei = int(arb_config.get(
                'min_profit_wei',
                self.web3.to_wei('0.1', 'ether')  # 0.1 ETH minimum profit
            ))
            self.profit_margin_multiplier = Decimal('1.5')  # 50% margin over costs
            
            # Gas configuration for mainnet
            self.base_gas = 300000
            self.gas_buffer_percent = 20
            
            # Safety parameters
            self.max_position_size = int(arb_config.get(
                'max_position_size',
                self.web3.to_wei('50', 'ether')  # 50 ETH max position
            ))
            self.max_price_impact = Decimal(str(arb_config.get('max_price_impact', '0.05')))
            self.slippage_tolerance = Decimal('0.02')  # 2% slippage tolerance
            
            # Mainnet-specific safety thresholds
            self.min_pool_size = self.web3.to_wei('50', 'ether')  # 50 ETH min pool size for testing, increase for mainnet
            self.max_gas_price = 500 * 10**9  # 500 GWEI max gas price
            self.min_profit_ratio = Decimal('1.5')  # Minimum 1.5x return on gas for testing, increase for mainnet
            self.max_position_percent = Decimal('0.05')  # Max 5% of pool size for testing, decrease for mainnet
            
            # Environment-specific configurations
            if self.web3.eth.chain_id == 1:  # Mainnet
                self.min_pool_size = self.web3.to_wei('500', 'ether')  # 500 ETH min pool size
                self.min_profit_ratio = Decimal('2')  # Minimum 2x return on gas
                self.max_position_percent = Decimal('0.03')  # Max 3% of pool size
            
            # Validate configuration
            self._validate_config()
            
            logger.info("Enhanced Arbitrage strategy initialized with mainnet configuration")
            
        except Exception as e:
            logger.error(f"Error initializing arbitrage strategy: {e}")
            raise
            
    def _load_abi(self, path: str) -> List:
        """Load and validate contract ABI."""
        try:
            with open(path, 'r') as f:
                abi = json.load(f)
            if not isinstance(abi, list):
                raise ValueError(f"Invalid ABI format in {path}")
            return abi
        except Exception as e:
            raise ValueError(f"Error loading ABI from {path}: {e}")

    def _validate_config(self):
        """Validate strategy configuration for mainnet deployment."""
        try:
            # Validate contract addresses
            required_addresses = {
                'Uniswap Router': self.uniswap_router,
                'Sushiswap Router': self.sushiswap_router,
                'Flash Loan Provider': self.flash_loan_provider
            }
            
            for name, address in required_addresses.items():
                if not address or not self.web3.is_address(address):
                    raise ValueError(f"Invalid {name} address: {address}")
                    
                # Verify contract code exists on mainnet
                code = self.web3.eth.get_code(address)
                if code == b'' or code == '0x':
                    raise ValueError(f"No contract code found at {name} address: {address}")
            
            # Validate profit thresholds
            if self.min_profit_wei < self.web3.to_wei('0.01', 'ether'):
                raise ValueError("Minimum profit too low for mainnet")
            
            # Validate position sizes
            if self.max_position_size > self.web3.to_wei('100', 'ether'):
                raise ValueError("Maximum position size too high for mainnet")
                
            # Validate gas settings
            if self.base_gas < 200000:
                raise ValueError("Base gas estimate too low for mainnet")
            if self.gas_buffer_percent < 10:
                raise ValueError("Gas buffer too low for mainnet safety")
                
            # Validate price impact and slippage settings
            if self.max_price_impact > Decimal('0.05'):
                raise ValueError("Price impact threshold too high for mainnet")
            if self.slippage_tolerance > Decimal('0.02'):
                raise ValueError("Slippage tolerance too high for mainnet")
                
            # Validate pool size requirements
            if self.min_pool_size < self.web3.to_wei('50', 'ether'):
                raise ValueError("Minimum pool size too low for mainnet safety")
                
            # Validate network
            chain_id = self.web3.eth.chain_id
            if chain_id != 1:  # Ethereum mainnet
                raise ValueError(f"Invalid network. Expected mainnet (1), got chain_id: {chain_id}")
                
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ValueError(f"Invalid mainnet configuration: {e}")

    async def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze transaction for arbitrage opportunity with mainnet-specific validation."""
        if not tx or not isinstance(tx, dict):
            logger.debug("Invalid transaction format")
            return None
            
        try:
            # Identify DEX and decode swap data
            swap_data = self.dex_handler.decode_swap_data(tx)
            if not swap_data:
                logger.debug("Failed to decode swap data")
                return None
            
            logger.debug(f"Decoded swap data: {swap_data}")
            
            # Get pool information for both DEXes
            pool_data_uni = await self.dex_handler.get_pool_info(
                'uniswap',
                swap_data['path'][0],
                swap_data['path'][1]
            )
            
            pool_data_sushi = await self.dex_handler.get_pool_info(
                'sushiswap',
                swap_data['path'][0],
                swap_data['path'][1]
            )
            
            if not pool_data_uni or not pool_data_sushi:
                logger.debug("Failed to get pool info")
                return None
            
            logger.debug(f"Uniswap pool data: {pool_data_uni}")
            logger.debug(f"Sushiswap pool data: {pool_data_sushi}")
            
            # Calculate optimal arbitrage amount
            arb_amount, profit = await self._calculate_optimal_arbitrage(
                pool_data_uni,
                pool_data_sushi,
                swap_data['path'][0],
                swap_data['path'][1]
            )
            
            logger.debug(f"Calculated arbitrage: amount={arb_amount}, profit={profit}")
            
            if not arb_amount or profit < self.min_profit_wei:
                logger.debug(f"Insufficient profit: {profit} < {self.min_profit_wei}")
                return None
            
            # Get current gas price and calculate gas costs
            try:
                gas_price = await self.web3.eth.get_gas_price()
                if callable(gas_price):
                    gas_price = await gas_price
                gas_price = int(gas_price)
            except Exception as e:
                logger.error(f"Error getting gas price: {e}")
                return None
            
            # Calculate total gas cost for mainnet conditions:
            # 1. Base transaction gas (21000)
            # 2. Flash loan borrow (300000)
            # 3. Flash loan repay (200000)
            # 4. First swap including approvals (180000)
            # 5. Second swap including approvals (180000)
            # 6. Safety margin for price updates (100000)
            estimated_gas = 981000  # Total estimated gas
            gas_cost = estimated_gas * gas_price
            
            # Add safety buffer for gas price spikes and failed txs (20%)
            gas_cost = int(gas_cost * Decimal('1.2'))
            
            # Calculate minimum required profit based on gas price
            # As gas price increases, required profit margin increases exponentially
            # This helps avoid unprofitable trades during high gas periods
            base_gas_price = 30 * 10**9  # 30 GWEI
            gas_multiplier = Decimal(str(gas_price)) / Decimal(str(base_gas_price))
            min_profit_multiplier = gas_multiplier ** Decimal('1.5')  # Exponential scaling
            
            required_profit = int(self.min_profit_wei * min_profit_multiplier)
            
            # Validate pool data
            for pool_name, pool_data in [('Uniswap', pool_data_uni), ('Sushiswap', pool_data_sushi)]:
                if not all(key in pool_data for key in ['reserves', 'fee', 'pair_address']):
                    logger.debug(f"Missing required data in {pool_name} pool")
                    return None
                if not all(key in pool_data['reserves'] for key in ['token0', 'token1']):
                    logger.debug(f"Missing reserve data in {pool_name} pool")
                    return None
                    
            # Calculate and validate prices
            uni_price = Decimal(str(pool_data_uni['reserves']['token1'])) / Decimal(str(pool_data_uni['reserves']['token0']))
            sushi_price = Decimal(str(pool_data_sushi['reserves']['token1'])) / Decimal(str(pool_data_sushi['reserves']['token0']))
            
            # Check for unrealistic prices (e.g., flash loan attacks)
            avg_price = (uni_price + sushi_price) / Decimal('2')
            max_deviation = Decimal('0.1')  # 10% max deviation
            
            if abs(uni_price - avg_price) / avg_price > max_deviation:
                logger.debug(f"Uniswap price deviation too high: {uni_price} vs avg {avg_price}")
                return None
            if abs(sushi_price - avg_price) / avg_price > max_deviation:
                logger.debug(f"Sushiswap price deviation too high: {sushi_price} vs avg {avg_price}")
                return None
            
            # Determine trading direction and validate reserves
            if uni_price < sushi_price:
                direction = 'buy_on_uniswap'
                buy_pool = pool_data_uni
                sell_pool = pool_data_sushi
            else:
                direction = 'buy_on_sushiswap'
                buy_pool = pool_data_sushi
                sell_pool = pool_data_uni
                
            # Validate minimum pool sizes (prevent manipulation)
            if Decimal(str(buy_pool['reserves']['token1'])) < self.min_pool_size:
                logger.debug(f"Buy pool ETH reserves too low: {float(buy_pool['reserves']['token1']) / 10**18:.2f} ETH < {float(self.min_pool_size) / 10**18:.2f} ETH required")
                return None
            if Decimal(str(sell_pool['reserves']['token1'])) < self.min_pool_size:
                logger.debug(f"Sell pool ETH reserves too low: {float(sell_pool['reserves']['token1']) / 10**18:.2f} ETH < {float(self.min_pool_size) / 10**18:.2f} ETH required")
                return None
            
            try:
                # Get reserves in correct order (token0 is USDC, token1 is WETH)
                buy_reserves = (
                    Decimal(str(buy_pool['reserves']['token0'])),  # USDC reserves
                    Decimal(str(buy_pool['reserves']['token1']))   # WETH reserves
                )
                sell_reserves = (
                    Decimal(str(sell_pool['reserves']['token0'])),  # USDC reserves
                    Decimal(str(sell_pool['reserves']['token1']))   # WETH reserves
                )
                
                # Validate reserve ratios (detect potential price manipulation)
                buy_ratio = buy_reserves[0] / buy_reserves[1]
                sell_ratio = sell_reserves[0] / sell_reserves[1]
                ratio_deviation = abs(buy_ratio - sell_ratio) / min(buy_ratio, sell_ratio)
                
                if ratio_deviation > Decimal('0.2'):  # 20% max ratio deviation
                    logger.debug(f"Reserve ratio deviation too high: {ratio_deviation:.2%}")
                    return None
                    
                # Check for minimum USDC liquidity
                min_usdc_liquidity = Decimal('1000000000000')  # $1M USDC
                if buy_reserves[0] < min_usdc_liquidity or sell_reserves[0] < min_usdc_liquidity:
                    logger.debug("Insufficient USDC liquidity in pools")
                    return None
                    
                # Validate block timestamps (prevent stale data)
                max_age = 300  # 5 minutes
                current_time = int(time.time())
                if current_time - buy_pool['block_timestamp_last'] > max_age:
                    logger.debug(f"Buy pool data too old: {current_time - buy_pool['block_timestamp_last']}s")
                    return None
                if current_time - sell_pool['block_timestamp_last'] > max_age:
                    logger.debug(f"Sell pool data too old: {current_time - sell_pool['block_timestamp_last']}s")
                    return None
                    
            except (KeyError, TypeError, ValueError) as e:
                logger.error(f"Error processing pool data: {e}")
                return None
            
            try:
                # Estimate real mainnet gas costs including:
                # 1. Base transaction (21000)
                # 2. Flash loan borrow (300000)
                # 3. Flash loan repay (200000)
                # 4. Token approvals (50000 each)
                # 5. DEX swaps (150000 each)
                # 6. Safety buffer for price updates (100000)
                estimated_gas = 971000
                
                # Add extra gas for first-time approvals if needed
                if not self._check_token_allowance(swap_data['path'][0]):
                    estimated_gas += 50000
                if not self._check_token_allowance(swap_data['path'][1]):
                    estimated_gas += 50000
                
                # Calculate gas costs
                try:
                    # Get base gas cost
                    base_cost = estimated_gas * gas_price
                    priority_fee = 2000000000  # Default 2 GWEI
                    
                    # Add priority fee for faster inclusion
                    try:
                        priority_fee = await self.web3.eth.max_priority_fee_per_gas
                    except Exception as e:
                        logger.warning(f"Error getting priority fee: {e}, using default")
                    
                    priority_cost = estimated_gas * priority_fee
                    
                    # Total gas cost with safety buffer
                    gas_cost = int((base_cost + priority_cost) * Decimal('1.2'))
                    
                    # Log detailed analysis
                    logger.debug(f"Network conditions:")
                    logger.debug(f"  Base gas price: {gas_price / 10**9:.2f} GWEI")
                    logger.debug(f"  Priority fee: {priority_fee / 10**9:.2f} GWEI")
                    logger.debug(f"  Estimated gas: {estimated_gas}")
                    logger.debug(f"Costs:")
                    logger.debug(f"  Base cost: {base_cost / 10**18:.4f} ETH")
                    logger.debug(f"  Priority cost: {priority_cost / 10**18:.4f} ETH")
                    logger.debug(f"  Total gas cost: {gas_cost / 10**18:.4f} ETH")
                    
                except Exception as e:
                    logger.error(f"Error calculating gas costs: {e}")
                    return None
                
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
                return None
            
            # Mainnet safety checks
            
            # 1. Basic profitability check with dynamic minimum based on gas price
            if net_profit < required_profit:
                logger.debug(f"Insufficient profit after gas: {net_profit / 10**18:.4f} ETH < {required_profit / 10**18:.4f} ETH required")
                return None
                
            # 2. Gas price safety threshold
            if gas_price > 1000 * 10**9:  # > 1000 GWEI
                logger.debug(f"Gas price too high for safe execution: {gas_price / 10**9:.2f} GWEI")
                return None
                
            # 3. Profit/gas ratio check
            profit_gas_ratio = Decimal(str(net_profit)) / Decimal(str(gas_cost))
            min_profit_ratio = Decimal('2')  # Minimum 2x return on gas costs
            if profit_gas_ratio < min_profit_ratio:
                logger.debug(f"Profit/gas ratio too low: {profit_gas_ratio:.2f}x (minimum {min_profit_ratio}x required)")
                return None
                
            # 4. Pool liquidity checks
            min_pool_reserves = Decimal(str(self.max_position_size)) * Decimal('10')  # Require 10x max position size in liquidity
            if buy_reserves[1] < min_pool_reserves:
                logger.debug(f"Buy pool reserves too low: {float(buy_reserves[1]) / 10**18:.2f} ETH < {float(min_pool_reserves) / 10**18:.2f} ETH required")
                return None
            if sell_reserves[1] < min_pool_reserves:
                logger.debug(f"Sell pool reserves too low: {float(sell_reserves[1]) / 10**18:.2f} ETH < {float(min_pool_reserves) / 10**18:.2f} ETH required")
                return None
                
            # 5. Price impact check
            amount_decimal = Decimal(str(arb_amount))
            buy_price_impact = (amount_decimal * Decimal('1000000')) / buy_reserves[1]  # Multiply by 1M for percentage
            sell_price_impact = (amount_decimal * Decimal('1000000')) / sell_reserves[1]
            max_price_impact = Decimal('5000')  # 0.5% max impact
            if buy_price_impact > max_price_impact or sell_price_impact > max_price_impact:
                logger.debug(f"Price impact too high: Buy {buy_price_impact/10000:.4f}% Sell {sell_price_impact/10000:.4f}% > {max_price_impact/10000:.4f}% max")
                return None
                
            # 6. Pending transactions check
            if buy_pool.get('pending_txs', []) or sell_pool.get('pending_txs', []):
                logger.debug("Pending transactions detected in pools")
                return None
            
            # Create arbitrage result
            result = {
                'type': 'arbitrage',
                'token_in': swap_data['path'][0],
                'token_out': swap_data['path'][1],
                'amount': arb_amount,
                'profit': profit,
                'gas_price': gas_price,
                'pools': {
                    'uniswap': pool_data_uni['pair_address'],
                    'sushiswap': pool_data_sushi['pair_address']
                },
                'timestamp': int(time.time())
            }
            logger.debug(f"Found arbitrage opportunity: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing arbitrage opportunity: {e}")
            return None

    async def _calculate_optimal_arbitrage(
        self,
        pool_uni: Dict,
        pool_sushi: Dict,
        token_in: str,
        token_out: str
    ) -> Tuple[int, int]:
        """Calculate optimal arbitrage amount between Uniswap and Sushiswap."""
        try:
            # Get pool reserves
            uni_reserve_in = pool_uni['reserves']['token0']
            uni_reserve_out = pool_uni['reserves']['token1']
            sushi_reserve_in = pool_sushi['reserves']['token0']
            sushi_reserve_out = pool_sushi['reserves']['token1']
            
            logger.debug(f"Pool reserves - Uniswap: in={uni_reserve_in}, out={uni_reserve_out}")
            logger.debug(f"Pool reserves - Sushiswap: in={sushi_reserve_in}, out={sushi_reserve_out}")
            
            # Calculate price difference
            uni_price = Decimal(str(uni_reserve_out)) / Decimal(str(uni_reserve_in))
            sushi_price = Decimal(str(sushi_reserve_out)) / Decimal(str(sushi_reserve_in))
            
            logger.debug(f"Prices - Uniswap: {uni_price}, Sushiswap: {sushi_price}")
            
            price_diff = abs(uni_price - sushi_price)
            logger.debug(f"Price difference: {price_diff}")
            
            if price_diff < Decimal('0.01'):  # 1% minimum price difference
                logger.debug("Insufficient price difference")
                return 0, 0
            
            # Determine direction (buy on cheaper, sell on more expensive)
            if uni_price < sushi_price:
                buy_pool = pool_uni
                sell_pool = pool_sushi
                buy_reserves = (uni_reserve_in, uni_reserve_out)
                sell_reserves = (sushi_reserve_in, sushi_reserve_out)
                logger.debug("Direction: Buy on Uniswap, Sell on Sushiswap")
            else:
                buy_pool = pool_sushi
                sell_pool = pool_uni
                buy_reserves = (sushi_reserve_in, sushi_reserve_out)
                sell_reserves = (uni_reserve_in, uni_reserve_out)
                logger.debug("Direction: Buy on Sushiswap, Sell on Uniswap")
            
            # Calculate optimal amount using binary search
            min_amount = self.web3.to_wei('0.1', 'ether')
            # Calculate max amount considering pool sizes and position limits
            # Use token1 (WETH) reserves since we're trading WETH
            max_pool_amount = min(
                buy_reserves[1] // 3,  # Max 33% of pool
                sell_reserves[1] // 3
            )
            max_amount = min(
                self.max_position_size,
                max_pool_amount
            )
            logger.debug(f"Max position size: {self.max_position_size}")
            logger.debug(f"Max pool amount: {max_pool_amount}")
            
            logger.debug(f"Search range: min={min_amount}, max={max_amount}")
            
            best_amount = 0
            best_profit = 0
            
            iteration = 0
            while min_amount <= max_amount and iteration < 100:  # Add iteration limit for safety
                iteration += 1
                test_amount = (min_amount + max_amount) // 2
                logger.debug(f"\nIteration {iteration}:")
                logger.debug(f"Testing amount: {test_amount} ({test_amount / 10**18:.4f} ETH)")
                
                # Calculate output from buy and sell
                buy_output = await self._simulate_swap_output(
                    test_amount,
                    buy_reserves[0],
                    buy_reserves[1],
                    buy_pool['fee']
                )
                logger.debug(f"Buy output: {buy_output} ({buy_output / 10**6:.4f} USDC)")
                
                if buy_output == 0:
                    logger.debug("Buy simulation failed")
                    max_amount = test_amount - 1
                    continue
                
                sell_output = await self._simulate_swap_output(
                    buy_output,
                    sell_reserves[0],
                    sell_reserves[1],
                    sell_pool['fee']
                )
                logger.debug(f"Sell output: {sell_output} ({sell_output / 10**18:.4f} ETH)")
                
                if sell_output == 0:
                    logger.debug("Sell simulation failed")
                    max_amount = test_amount - 1
                    continue
                
                profit = sell_output - test_amount
                logger.debug(f"Current profit: {profit} ({profit / 10**18:.4f} ETH)")
                
                if profit > best_profit:
                    best_profit = profit
                    best_amount = test_amount
                    min_amount = test_amount + 1
                    logger.debug(f"New best profit: {best_profit} ({best_profit / 10**18:.4f} ETH)")
                    logger.debug(f"New best amount: {best_amount} ({best_amount / 10**18:.4f} ETH)")
                else:
                    max_amount = test_amount - 1
                    logger.debug("No improvement, reducing max amount")
            
            logger.debug(f"Final result - amount: {best_amount} ({best_amount / 10**18:.4f} ETH), profit: {best_profit} ({best_profit / 10**18:.4f} ETH)")
            return best_amount, best_profit
            
        except Exception as e:
            logger.error(f"Error calculating optimal arbitrage: {e}")
            return 0, 0

    async def execute_opportunity(self, opportunity: Dict) -> bool:
        """Execute arbitrage opportunity using flash loans through Flashbots."""
        if not opportunity or opportunity['type'] != 'arbitrage':
            return False
            
        try:
            # Calculate total flash loan amount needed
            total_loan_amount = opportunity['amount']
            
            # Encode the arbitrage strategy callback for the flash loan
            callback_data = self._encode_strategy_callback(
                'arbitrage',
                opportunity['token_in'],
                opportunity['token_out'],
                total_loan_amount,
                opportunity['pools']['uniswap'],  # Pass both pool addresses
                sushi_pool=opportunity['pools']['sushiswap']
            )
            
            # Execute the arbitrage using flash loan through Flashbots
            success, profit = await self._execute_with_flash_loan(
                opportunity['token_in'],
                total_loan_amount,
                callback_data,
                opportunity['gas_price']
            )
            
            if success:
                logger.info(
                    f"Successfully executed arbitrage:\n"
                    f"Profit: {profit} ETH\n"
                    f"Amount: {opportunity['amount']}\n"
                    f"Pools: {opportunity['pools']}"
                )
            else:
                logger.warning("Failed to execute arbitrage opportunity")
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing arbitrage opportunity: {e}")
            return False

    def _check_token_allowance(self, token_address: str) -> bool:
        """Check if we have sufficient token allowance for flash loan and DEX contracts."""
        try:
            token_contract = self.web3.eth.contract(
                address=token_address,
                abi=self.token_abi
            )
            
            # Get our contract address
            arb_contract = self.web3.eth.contract(
                address=self.contract_address,
                abi=self.arbitrage_abi
            )
            
            # Check allowances for all required contracts
            contracts_to_check = [
                self.flash_loan_provider,  # Flash loan provider
                self.uniswap_router,      # Uniswap router
                self.sushiswap_router,    # Sushiswap router
                arb_contract.address      # Our arbitrage contract
            ]
            
            min_allowance = self.web3.to_wei('1000000', 'ether')  # 1M tokens
            
            for contract in contracts_to_check:
                try:
                    allowance = token_contract.functions.allowance(
                        self.account.address,
                        contract
                    ).call()
                    
                    if allowance < min_allowance:
                        logger.debug(f"Insufficient allowance for {token_address} on {contract}")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error checking allowance for {contract}: {e}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error checking token allowance: {e}")
            return False

    async def _simulate_swap_output(
        self,
        amount_in: int,
        reserve_in: int,
        reserve_out: int,
        fee: Decimal
    ) -> int:
        """Simulate swap output with precise calculations and slippage protection."""
        try:
            # Validate inputs
            if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
                logger.debug("Invalid swap parameters")
                return 0
                
            # Check maximum input amount (prevent price manipulation)
            max_input_percent = Decimal('0.03')  # Max 3% of reserves
            max_input = Decimal(str(reserve_in)) * max_input_percent
            
            if Decimal(str(amount_in)) > max_input:
                logger.debug(f"Input amount too large: {amount_in} > {max_input}")
                return 0
                
            # Calculate output with fee
            amount_in_with_fee = Decimal(str(amount_in)) * (Decimal('1') - fee)
            numerator = amount_in_with_fee * Decimal(str(reserve_out))
            denominator = Decimal(str(reserve_in)) + amount_in_with_fee
            
            # Apply safety buffer for mainnet conditions
            output = int(numerator / denominator)
            safety_buffer = Decimal('0.995')  # 0.5% safety margin
            
            return int(Decimal(str(output)) * safety_buffer)
            
        except Exception as e:
            logger.error(f"Error simulating swap output: {e}")
            return 0
