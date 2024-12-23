"""Optimization modules for arbitrage strategies."""
import asyncio
from decimal import Decimal
import time
import random
from typing import Dict, List, Tuple, Optional, Any
from web3 import Web3
from web3.exceptions import TransactionNotFound, TimeExhausted
import websockets
from concurrent.futures import ThreadPoolExecutor
import logging

from .exceptions import (
    RiskLimitExceeded,
    CircuitBreakerTriggered,
    ExposureLimitExceeded,
    SlippageExceeded,
    MEVCompetitionError,
    InsufficientLiquidityError,
    NetworkError,
    GasError,
    PositionSizeError
)

logger = logging.getLogger(__name__)

class BaseOptimizer:
    """Base class for optimization modules."""
    
    def __init__(self, w3: Web3, config: Optional[Dict[str, Any]] = None):
        self.w3 = w3
        self.config = config or {}
        
        # Set default values if config is None or missing keys
        gas_config = self.config.get('gas', {})
        self.max_gas_price = w3.to_wei(gas_config.get('max_gas_price', 300), 'gwei')
        
        risk_config = self.config.get('risk', {})
        self.max_slippage = Decimal(str(risk_config.get('max_slippage', '0.02')))
        self.min_liquidity = w3.to_wei(int(risk_config.get('min_liquidity', '2')), 'ether')
        
        latency_config = self.config.get('optimization', {}).get('latency', {})
        self.thread_pool = ThreadPoolExecutor(
            max_workers=latency_config.get('parallel_requests', 4)
        )

class GasOptimizer(BaseOptimizer):
    """Optimizes gas usage and pricing strategies."""

    def __init__(self, w3: Web3, config: Dict[str, Any]):
        super().__init__(w3, config)
        self.estimation_buffer = Decimal(str(config['gas']['estimation_buffer']))
        self.min_profit_after_gas = int(config['gas']['min_profit_after_gas'])
        self.gas_limits = config['gas']['gas_limits']
        self.priority_fee = int(config['gas']['priority_fee'])
        self.max_priority_fee = int(config['gas']['max_priority_fee'])

    async def estimate_optimal_gas_price(self, strategy: str) -> int:
        """Calculate optimal gas price based on strategy and market conditions."""
        try:
            # Get latest block for base fee
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            
            # Different strategies need different gas price premiums
            premiums = {
                'arbitrage': Decimal('1.1'),  # 10% premium
                'jit': Decimal('1.2'),        # 20% premium
                'sandwich': Decimal('1.3')     # 30% premium
            }
            
            premium = premiums.get(strategy, Decimal('1.1'))
            
            # Calculate gas price with premium and priority fee
            gas_price = int(base_fee * premium) + self.priority_fee
            
            # Apply estimation buffer for safety
            gas_price = int(Decimal(str(gas_price)) * self.estimation_buffer)
            
            if gas_price > self.max_gas_price:
                raise GasError(f"Gas price {gas_price} exceeds maximum {self.max_gas_price}")
                
            return gas_price
            
        except Exception as e:
            logger.error(f"Error estimating gas price: {e}")
            raise GasError(f"Failed to estimate gas price: {e}")

    async def calculate_competitive_gas_price(
        self,
        base_fee: int,
        competitor_premium: int
    ) -> int:
        """Calculate gas price accounting for competition."""
        try:
            # Calculate competitive gas price
            competitive_price = base_fee + competitor_premium + self.priority_fee
            
            # Apply estimation buffer
            safe_price = int(Decimal(str(competitive_price)) * self.estimation_buffer)
            
            return min(safe_price, self.max_gas_price)
            
        except Exception as e:
            logger.error(f"Error calculating competitive gas price: {e}")
            raise GasError(f"Failed to calculate competitive gas price: {e}")

    async def validate_gas_cost(
        self,
        gas_price: int,
        gas_limit: int,
        expected_profit: int
    ) -> bool:
        """Validate if gas costs allow for minimum profit."""
        try:
            gas_cost = gas_price * gas_limit
            profit_after_gas = expected_profit - gas_cost
            
            return profit_after_gas >= self.min_profit_after_gas
            
        except Exception as e:
            logger.error(f"Error validating gas cost: {e}")
            raise GasError(f"Failed to validate gas cost: {e}")

class LatencyOptimizer(BaseOptimizer):
    """Optimizes transaction timing and network latency handling."""

    def __init__(self, w3_http: Web3, w3_ws: Optional[Web3] = None, config: Optional[Dict[str, Any]] = None):
        # Set default config if none provided
        if config is None:
            config = {
                'optimization': {
                    'latency': {
                        'max_acceptable': 0.1,
                        'warning_threshold': 0.08,
                        'critical_threshold': 0.15,
                        'max_retries': 3,
                        'retry_delay': 0.05,
                        'ws_ping_interval': 5,
                        'ws_timeout': 3,
                        'parallel_requests': 4
                    },
                    'mempool': {
                        'max_pending_tx': 5000,
                        'cleanup_interval': 100,
                        'max_age_seconds': 60
                    }
                }
            }

        super().__init__(w3_http, config)
        self.ws_w3 = w3_ws
        self.ws_connections = []  # Initialize empty list for WS connections
        
        # Get config values with defaults
        latency_config = config['optimization']['latency']
        mempool_config = config['optimization']['mempool']
        
        self.max_latency = float(latency_config['max_acceptable'])
        self.warning_threshold = float(latency_config['warning_threshold'])
        self.critical_threshold = float(latency_config['critical_threshold'])
        self.max_retries = int(latency_config['max_retries'])
        self.retry_delay = float(latency_config['retry_delay'])
        self.ws_ping_interval = int(latency_config['ws_ping_interval'])
        self.ws_timeout = int(latency_config['ws_timeout'])
        self.parallel_requests = int(latency_config['parallel_requests'])
        
        self.pending_txs_cache = {}
        self._classification_cache = {}
        self.cache_cleanup_counter = 0
        self.cache_cleanup_interval = int(mempool_config['cleanup_interval'])
        
        self.websocket_kwargs = {
            'ping_interval': self.ws_ping_interval,
            'ping_timeout': self.ws_timeout,
            'max_size': 2**23,
            'max_queue': 2**10,
            'compression': None
        }

    async def start_mempool_monitoring(
        self,
        max_pending_tx: Optional[int] = None,
        block_time: Optional[int] = None
    ) -> None:
        """Start monitoring mempool with optimized settings."""
        try:
            max_pending_tx = max_pending_tx or int(self.config['optimization']['mempool']['max_pending_tx'])
            block_time = block_time or int(self.config['network']['block_time'])
            
            # Initialize WebSocket connections if available
            self.ws_connections = []
            if self.ws_w3 is not None:
                try:
                    for _ in range(self.parallel_requests):
                        ws_provider = Web3.WebsocketProvider(
                            self.ws_w3.provider.endpoint_uri,
                            websocket_timeout=self.ws_timeout,
                            websocket_kwargs=self.websocket_kwargs
                        )
                        ws_w3 = Web3(ws_provider)
                        self.ws_connections.append(ws_w3)

                    # Subscribe to pending transactions on all connections
                    self.pending_filters = [
                        ws.eth.filter('pending')
                        for ws in self.ws_connections
                    ]
                except Exception as e:
                    logger.warning(f"Failed to initialize WebSocket connections: {e}. Falling back to HTTP.")
                    self.ws_connections = []

            # If no WebSocket connections, use HTTP filter
            if not self.ws_connections:
                logger.info("Using HTTP filter for mempool monitoring")
                self.pending_filters = [self.w3.eth.filter('pending')]
            
            self.max_pending = max_pending_tx
            self.target_block_time = block_time
            self.monitoring_active = True
            
            logger.info("Mempool monitoring started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start mempool monitoring: {e}")
            raise NetworkError(f"Failed to start mempool monitoring: {e}")

    async def get_new_transactions(self) -> List[Dict[str, Any]]:
        """Get new transactions with parallel processing."""
        if not self.monitoring_active:
            return []
            
        try:
            # Get new transaction hashes
            all_tx_hashes = set()
            
            if self.ws_connections:
                # Use parallel WebSocket connections
                tasks = [
                    self.thread_pool.submit(filter.get_new_entries)
                    for filter in self.pending_filters
                ]
                
                for future in tasks:
                    tx_hashes = future.result()
                    all_tx_hashes.update(tx_hashes)
            else:
                # Use HTTP filter
                try:
                    tx_hashes = self.pending_filters[0].get_new_entries()
                    all_tx_hashes.update(tx_hashes)
                except Exception as e:
                    logger.warning(f"Error getting transactions via HTTP: {e}")

            # Process transactions in parallel with size limit
            transactions = []
            tx_tasks = []
            
            for tx_hash in list(all_tx_hashes)[:self.max_pending]:
                if tx_hash in self.pending_txs_cache:
                    transactions.append(self.pending_txs_cache[tx_hash])
                    continue
                    
                task = self.thread_pool.submit(
                    self._get_transaction_with_timeout,
                    tx_hash
                )
                tx_tasks.append((tx_hash, task))

            # Collect results with timeout
            for tx_hash, task in tx_tasks:
                try:
                    tx = task.result(timeout=self.retry_delay)
                    if tx:
                        self.pending_txs_cache[tx_hash] = tx
                        transactions.append(tx)
                except Exception as e:
                    logger.debug(f"Failed to get transaction {tx_hash}: {e}")
                    continue

            # Cleanup cache periodically
            self.cache_cleanup_counter += 1
            if self.cache_cleanup_counter >= self.cache_cleanup_interval:
                self._cleanup_cache()
                self.cache_cleanup_counter = 0

            return transactions
            
        except Exception as e:
            logger.error(f"Failed to get new transactions: {e}")
            raise NetworkError(f"Failed to get new transactions: {e}")

    def _cleanup_cache(self) -> None:
        """Clean up old entries from caches."""
        try:
            current_time = time.time()
            max_age = int(self.config['optimization']['mempool']['max_age_seconds'])
            
            # Clean transaction cache
            self.pending_txs_cache = {
                k: v for k, v in self.pending_txs_cache.items()
                if current_time - v.get('timestamp', 0) < max_age
            }
            
            # Clean classification cache
            self._classification_cache = {
                k: v for k, v in self._classification_cache.items()
                if k in self.pending_txs_cache
            }
            
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")

    def _get_transaction_with_timeout(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get transaction with timeout."""
        try:
            if self.ws_connections:
                # Use the least loaded WebSocket connection
                ws = min(self.ws_connections, key=lambda x: x.provider.request_counter)
                web3_instance = ws
            else:
                # Use HTTP connection
                web3_instance = self.w3

            tx = web3_instance.eth.get_transaction(tx_hash)
            if tx:
                tx['timestamp'] = time.time()  # Add timestamp for cache management
            return tx
        except Exception as e:
            logger.debug(f"Error getting transaction {tx_hash}: {e}")
            return None

    async def simulate_network_conditions(
        self,
        base_fee: int,
        block_usage: float,
        latency: float,
        packet_loss: float
    ) -> None:
        """Simulate network conditions for testing."""
        try:
            # Store simulation parameters
            self.simulated_base_fee = base_fee
            self.simulated_block_usage = block_usage
            self.simulated_latency = latency
            self.simulated_packet_loss = packet_loss
            
            # Apply network conditions
            async def apply_network_conditions():
                # Simulate network latency
                await asyncio.sleep(latency)
                
                # Simulate packet loss
                if random.random() < packet_loss:
                    raise NetworkError("Simulated packet loss")
                
                # Update block parameters
                block = self.w3.eth.get_block('latest')
                block.baseFeePerGas = base_fee
                block.gasUsed = int(block.gasLimit * block_usage)
                
                return block
            
            # Test network conditions
            await apply_network_conditions()
            
            # Apply latency to WebSocket connections if available
            for ws in getattr(self, 'ws_connections', []):
                if hasattr(ws.provider, 'websocket_kwargs'):
                    ws.provider.websocket_kwargs['latency'] = latency
                    
            logger.info(
                f"Network conditions simulated successfully:\n"
                f"Base Fee: {base_fee} wei\n"
                f"Block Usage: {block_usage * 100}%\n"
                f"Latency: {latency * 1000}ms\n"
                f"Packet Loss: {packet_loss * 100}%"
            )
            
        except Exception as e:
            logger.error(f"Failed to simulate network conditions: {e}")
            raise NetworkError(f"Failed to simulate network conditions: {e}")

    def classify_transaction(self, tx: Dict[str, Any]) -> str:
        """Classify transaction type based on characteristics."""
        try:
            # Check cache first
            tx_hash = tx.get('hash', '').hex()
            if tx_hash in self._classification_cache:
                return self._classification_cache[tx_hash]
            
            # Default classification
            classification = 'standard'
            
            # Check for potential MEV characteristics
            if tx.get('data') and len(tx['data']) > 2:  # Has calldata
                if 'flash' in tx['data'].hex().lower():
                    classification = 'flash_loan'
                elif any(sig in tx['data'].hex().lower() for sig in ['swap', 'exact', 'token']):
                    classification = 'potential_mev'
                    
            # Cache the result
            self._classification_cache[tx_hash] = classification
            return classification
            
        except Exception as e:
            logger.error(f"Error classifying transaction: {e}")
            return 'unknown'

    async def reconnect_websocket(self) -> None:
        """Reconnect WebSocket connection with optimized settings."""
        try:
            # Close existing connections
            for ws in self.ws_connections:
                if hasattr(ws.provider, 'disconnect'):
                    await ws.provider.disconnect()
            
            # Create new connections
            self.ws_connections = []
            for _ in range(self.parallel_requests):
                ws_provider = Web3.WebsocketProvider(
                    self.ws_w3.provider.endpoint_uri,
                    websocket_timeout=self.ws_timeout,
                    websocket_kwargs=self.websocket_kwargs
                )
                ws_w3 = Web3(ws_provider)
                self.ws_connections.append(ws_w3)
                
            logger.info("WebSocket connections successfully reconnected")
            
        except Exception as e:
            logger.error(f"Failed to reconnect WebSocket: {e}")
            raise NetworkError(f"Failed to reconnect WebSocket: {e}")

    async def measure_ws_latency(self, ws: Optional[Web3] = None) -> float:
        """Measure WebSocket connection latency with optimization."""
        ws = ws or self.ws_w3
        try:
            start_time = time.time()
            # Use eth_blockNumber as it's lighter than getting full block
            block_number = ws.eth.block_number
            latency = time.time() - start_time
            
            # Log warnings if latency exceeds thresholds
            if latency > self.critical_threshold:
                logger.critical(f"Critical latency detected: {latency:.3f}s")
            elif latency > self.warning_threshold:
                logger.warning(f"High latency detected: {latency:.3f}s")
                
            return latency
            
        except Exception as e:
            logger.error(f"Failed to measure latency: {e}")
            raise NetworkError(f"Failed to measure latency: {e}")

    async def estimate_profit_potential(self, tx: Dict[str, Any]) -> int:
        """Estimate potential profit from a transaction."""
        try:
            # Get transaction type from cache or classify
            tx_type = self._classification_cache.get(
                tx.get('hash', '').hex(),
                self.classify_transaction(tx)
            )
            
            # Default profit estimate
            estimated_profit = 0
            
            if tx_type == 'flash_loan':
                # Estimate flash loan profit based on size and typical returns
                value = tx.get('value', 0)
                if value > 0:
                    # Assume 0.1-0.5% profit potential on flash loans
                    estimated_profit = int(value * random.uniform(0.001, 0.005))
                    
            elif tx_type == 'potential_mev':
                # Estimate MEV profit based on gas price and typical ranges
                gas_price = tx.get('gasPrice', 0)
                if gas_price > 0:
                    # Higher gas price often indicates higher MEV potential
                    base_profit = int(gas_price * random.uniform(10, 50))
                    # Scale profit by transaction complexity
                    data_length = len(tx.get('data', '0x')) - 2  # Subtract '0x'
                    complexity_multiplier = min(data_length / 1000, 5)  # Cap at 5x
                    estimated_profit = int(base_profit * complexity_multiplier)
            
            # Ensure profit meets minimum threshold
            min_profit = int(self.config['optimization']['mempool'].get(
                'min_profit_threshold',
                self.config['risk']['min_profit_threshold']
            ))
            
            return max(estimated_profit, min_profit)
            
        except Exception as e:
            logger.error(f"Error estimating profit potential: {e}")
            return 0

class PositionOptimizer(BaseOptimizer):
    """Optimizes position sizes and entry/exit timing."""

    def __init__(self, w3: Web3, config: Dict[str, Any]):
        super().__init__(w3, config)
        self.min_trade = int(config['optimization']['position_sizing']['min_trade'])
        self.max_trade = int(config['optimization']['position_sizing']['max_trade'])
        self.increment = int(config['optimization']['position_sizing']['increment'])
        self.max_pool_impact = Decimal(str(config['optimization']['position_sizing']['max_pool_impact']))

    async def calculate_safe_position(
        self,
        max_position: int,
        current_volatility: float
    ) -> int:
        """Calculate safe position size based on current conditions."""
        try:
            # Reduce position size as volatility increases
            volatility_factor = Decimal('1') - Decimal(str(current_volatility))
            safe_position = int(Decimal(str(max_position)) * volatility_factor)
            
            # Ensure position is within configured limits
            safe_position = max(min(safe_position, self.max_trade), self.min_trade)
            
            if safe_position < self.min_liquidity:
                raise PositionSizeError("Position size below minimum threshold")
                
            return safe_position
            
        except Exception as e:
            logger.error(f"Error calculating safe position: {e}")
            raise PositionSizeError(f"Failed to calculate safe position: {e}")

class RiskManager(BaseOptimizer):
    """Manages trading risks and exposure."""

    def __init__(self, w3: Web3, config: Dict[str, Any]):
        super().__init__(w3, config)
        self.circuit_breakers = config['risk']['circuit_breakers']
        self.exposure_limits = config['risk']['exposure_limits']
        self.consecutive_failures = 0
        self.last_reset_time = time.time()

    async def validate_trade(
        self,
        position_size: int,
        expected_profit: int,
        gas_cost: int
    ) -> Tuple[bool, str]:
        """Validate if trade meets risk parameters."""
        try:
            # Check consecutive failures
            if self.consecutive_failures >= self.circuit_breakers['consecutive_failures']:
                return False, "Too many consecutive failures"
            
            # Check position size limits
            if position_size > int(self.exposure_limits['single_trade']):
                return False, "Position size exceeds single trade limit"
            
            # Check profit after gas
            profit_after_gas = expected_profit - gas_cost
            if profit_after_gas < int(self.config['gas']['min_profit_after_gas']):
                return False, "Insufficient profit after gas costs"
            
            return True, "Trade validated successfully"
            
        except Exception as e:
            logger.error(f"Error validating trade: {e}")
            raise RiskLimitExceeded(f"Failed to validate trade: {e}")

    async def update_metrics(self, success: bool) -> None:
        """Update risk metrics based on trade result."""
        try:
            if success:
                self.consecutive_failures = 0
            else:
                self.consecutive_failures += 1
                
            # Reset metrics periodically
            current_time = time.time()
            if current_time - self.last_reset_time > self.config['monitoring']['recovery_time']:
                self.consecutive_failures = 0
                self.last_reset_time = current_time
                
        except Exception as e:
            logger.error(f"Error updating risk metrics: {e}")
