"""Enhanced arbitrage bot with improved DEX validation and transaction processing."""
import os
import json
import time
import asyncio
from web3 import Web3
from typing import Dict, List, Optional
from decimal import Decimal

from .utils.dex_utils import DEXValidator
from .utils.method_signatures_new import get_method_info, is_dex_related
from .strategies_new import EnhancedFrontRunStrategy
from .logger_config import logger
from .utils import (
    setup_web3,
    get_pending_transactions,
    estimate_gas_price
)
from .flashbots import FlashbotsManager

class EnhancedArbitrageBot:
    """Enhanced arbitrage bot with improved validation and monitoring."""
    
    def __init__(self, web3: Web3, flash_loan_contract_address: str):
        """Initialize the ArbitrageBot with proper error handling and validation."""
        logger.debug(f"Initializing Enhanced ArbitrageBot with flash loan contract: {flash_loan_contract_address}")
        
        # Create necessary directories
        os.makedirs('logs', exist_ok=True)
        
        # Initialize state variables with performance optimizations
        self._running = False
        self._tasks = []
        self._pending_tx_cache = {}
        self._cache_ttl = 5  # Cache TTL in seconds
        self._last_cache_clear = time.time()
        
        # Validate Web3 connection
        if not web3.is_connected():
            raise ConnectionError("Web3 instance is not connected")
        self.w3 = web3
        
        # Load and validate configuration
        try:
            with open('config/config.json', 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("config/config.json not found")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in config.json")
            
        # Initialize components with optimizations
        self.dex_validator = DEXValidator(self.config)
        
        # Initialize strategies with profitability focus
        self.strategies = {}
        if self.config['strategies']['frontrun']['enabled']:
            self.strategies['frontrun'] = EnhancedFrontRunStrategy(web3, self.config)
            
        if not self.strategies:
            raise ValueError("No strategies enabled in configuration")
            
        # Initialize Flashbots for MEV protection
        flashbots_key = os.getenv('FLASHBOTS_PRIVATE_KEY')
        if flashbots_key:
            self.flashbots = FlashbotsManager(
                web3,
                flashbots_key,
                os.getenv('FLASHBOTS_RELAY_URL', 'https://relay.flashbots.net')
            )
        else:
            self.flashbots = None
            
        logger.info("Enhanced ArbitrageBot initialized successfully")

    async def start(self) -> None:
        """Start the arbitrage bot with optimized monitoring."""
        if self._running:
            logger.warning("Bot is already running")
            return
            
        logger.info("Starting enhanced arbitrage bot...")
        self._running = True
        
        # Create monitoring tasks with different priorities
        tasks = [
            self._create_task(self.run_monitoring_loop(), "Main Monitoring"),
            self._create_task(self._run_health_check(), "Health Check"),
            self._create_task(self._run_cache_cleanup(), "Cache Cleanup")
        ]
        
        self._tasks.extend(tasks)

    async def stop(self) -> None:
        """Stop the arbitrage bot gracefully."""
        logger.info("Stopping enhanced arbitrage bot...")
        self._running = False
        
        # Cancel all tasks with proper cleanup
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
        self._tasks.clear()
        logger.info("Enhanced arbitrage bot stopped")

    def _create_task(self, coro, name: str) -> asyncio.Task:
        """Create a named task with error handling."""
        task = asyncio.create_task(coro, name=name)
        task.add_done_callback(self._handle_task_result)
        return task

    def _handle_task_result(self, task: asyncio.Task) -> None:
        """Handle task completion and errors."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Task {task.get_name()} failed: {e}", exc_info=True)

    async def run_monitoring_loop(self) -> None:
        """Enhanced monitoring loop with improved transaction processing."""
        logger.info("Starting enhanced monitoring loop...")
        retry_count = 0
        max_retries = 3
        
        while self._running:
            try:
                # Check Web3 connection
                if not self.w3.is_connected():
                    logger.error("Lost connection to Web3 provider")
                    await self._handle_connection_error()
                    continue
                
                # Get pending transactions with caching
                try:
                    current_block = await self.w3.eth.block_number
                    cache_key = f"block_{current_block}"
                    
                    if cache_key in self._pending_tx_cache:
                        pending_txs = self._pending_tx_cache[cache_key]
                    else:
                        pending_txs = await asyncio.wait_for(
                            asyncio.to_thread(get_pending_transactions, self.w3),
                            timeout=10
                        )
                        self._pending_tx_cache[cache_key] = pending_txs
                        
                except asyncio.TimeoutError:
                    logger.error("Timeout getting pending transactions")
                    continue
                    
                # Process transactions in parallel for better performance
                if pending_txs:
                    tasks = []
                    for tx in pending_txs:
                        if not self._running:
                            break
                        tasks.append(self._process_transaction(tx))
                        
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        successful = sum(1 for r in results if r and not isinstance(r, Exception))
                        logger.info(f"Processed {successful} valid transactions out of {len(tasks)} total")
                
                # Reset retry count on success
                retry_count = 0
                
                # Dynamic sleep based on activity
                sleep_time = 0.1 if pending_txs else 1
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                retry_count += 1
                
                if retry_count >= max_retries:
                    logger.critical("Max retries reached, stopping bot")
                    await self.stop()
                    break
                    
                await asyncio.sleep(2 ** retry_count)

    async def _process_transaction(self, tx: Dict) -> bool:
        """Process a single transaction with enhanced validation and profitability checks."""
        try:
            # Get method info
            method_id = tx.get('input', '')[:10]
            method_info = get_method_info(method_id)
            
            # Quick validation
            if not is_dex_related(method_id):
                return False
                
            # Log minimal transaction details
            logger.debug(f"Processing transaction: {tx.get('hash', 'NO_HASH').hex()}")
            
            # Analyze with each strategy
            for strategy_name, strategy in self.strategies.items():
                try:
                    opportunity = await asyncio.wait_for(
                        strategy.analyze_transaction(tx),
                        timeout=2
                    )
                    
                    if opportunity:
                        await self._handle_opportunity(opportunity)
                        return True
                        
                except asyncio.TimeoutError:
                    logger.warning(f"Strategy {strategy_name} timed out")
                except Exception as e:
                    logger.error(f"Error in strategy {strategy_name}: {e}")
                    
            return False
            
        except Exception as e:
            logger.error(f"Error processing transaction: {e}")
            return False

    async def _handle_opportunity(self, opportunity: Dict) -> None:
        """Handle identified arbitrage opportunity with profit optimization."""
        try:
            # Calculate profit metrics with gas optimization
            expected_profit = float(opportunity.get('expected_profit', '0').split()[0])
            gas_price = await self.w3.eth.gas_price
            estimated_gas = 500000  # Conservative estimate
            gas_cost = float(Web3.from_wei(gas_price * estimated_gas, 'ether'))
            net_profit = expected_profit - gas_cost
            
            # Log opportunity details
            logger.info(
                f"\n{'!'*50}"
                f"\nOPPORTUNITY FOUND!"
                f"\n  Strategy: {opportunity.get('type', 'unknown')}"
                f"\n  Expected Profit: {expected_profit} ETH"
                f"\n  Gas Cost: {gas_cost} ETH"
                f"\n  Net Profit: {net_profit} ETH"
                f"\n  DEX: {opportunity.get('dex', 'Unknown')}"
            )
            
            # Execute if profitable
            if net_profit > 0:
                strategy = self.strategies.get(opportunity['type'])
                if strategy:
                    success = await strategy.execute_opportunity(opportunity)
                    if success:
                        logger.info(f"Successfully executed opportunity with {net_profit} ETH profit")
                    else:
                        logger.warning("Failed to execute opportunity")
                        
        except Exception as e:
            logger.error(f"Error handling opportunity: {e}")

    async def _run_health_check(self) -> None:
        """Run periodic health checks."""
        while self._running:
            try:
                # Check Web3 connection
                if not self.w3.is_connected():
                    logger.error("Web3 connection lost in health check")
                    
                # Check gas price
                gas_price = await self.w3.eth.gas_price
                if gas_price > self.config.get('max_gas_price', 100e9):
                    logger.warning(f"High gas price detected: {gas_price}")
                    
                await asyncio.sleep(30)  # Run every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {e}")
                await asyncio.sleep(5)

    async def _run_cache_cleanup(self) -> None:
        """Clean up expired cache entries."""
        while self._running:
            try:
                current_time = time.time()
                if current_time - self._last_cache_clear > self._cache_ttl:
                    self._pending_tx_cache.clear()
                    self._last_cache_clear = current_time
                    
                await asyncio.sleep(self._cache_ttl)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
                await asyncio.sleep(5)

    async def _handle_connection_error(self) -> None:
        """Handle Web3 connection errors with retry logic."""
        retry_count = 0
        max_retries = 3
        
        while self._running and retry_count < max_retries:
            try:
                self.w3 = setup_web3()
                if self.w3.is_connected():
                    logger.info("Successfully reconnected to Web3 provider")
                    return
            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")
                
            retry_count += 1
            await asyncio.sleep(2 ** retry_count)
            
        logger.critical("Failed to reconnect to Web3 provider")
        await self.stop()
