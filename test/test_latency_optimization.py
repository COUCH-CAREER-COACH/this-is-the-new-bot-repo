"""Test suite for latency optimization with real-world scenarios."""
import os
import pytest
import asyncio
from decimal import Decimal
from web3 import Web3
from web3.exceptions import TransactionNotFound, TimeExhausted
import json
import time
import random
import statistics
from web3.providers import HTTPProvider, WebsocketProvider
from typing import List, Dict, Any, Optional, Tuple, Union
from src.optimizations import LatencyOptimizer
from src.metrics_collector import MetricsCollector
from src.exceptions import (
    ConnectionError,
    TransactionError,
    LatencyError,
    NetworkError
)
from src.logger_config import get_logger

# Get logger for this module
logger = get_logger('test_latency')

class TestLatencyOptimization:
    @classmethod
    def setup_class(cls):
        """Set up class-level attributes."""
        try:
            # Initialize Web3
            provider = HTTPProvider('http://localhost:8545')
            cls.web3 = Web3(provider)
            
            # Initialize other attributes
            cls.config = None
            cls.metrics = None
            cls.ws_connections = []
            cls.test_metrics = {}
            cls.start_time = None
            
            # Ensure web3 connection
            if not cls.web3.is_connected():
                raise NetworkError("Web3 connection failed")
            
        except Exception as e:
            logger.error(f"Failed to initialize test class: {e}")
            raise

    async def verify_network_conditions(self):
        """Verify network conditions meet mainnet requirements."""
        try:
            # Check node connectivity
            if not self.web3.is_connected():
                raise NetworkError("Web3 connection failed")
            
            # Check block sync
            latest_block = self.web3.eth.get_block('latest')
            if latest_block is None:
                raise NetworkError("Failed to get latest block")
            
            # Verify WebSocket connections if available
            if self.ws_connections:
                for ws in self.ws_connections:
                    if hasattr(ws, 'is_connected') and ws.is_connected():
                        try:
                            latency = await self.optimizer.measure_ws_latency(ws)
                            assert latency <= self.config['optimization']['latency']['max_acceptable'], \
                                f"WebSocket latency {latency*1000:.2f}ms exceeds threshold"
                        except Exception as e:
                            logger.warning(f"WebSocket latency check failed: {e}")
            
            return True
        except Exception as e:
            if hasattr(self, 'metrics') and self.metrics is not None:
                try:
                    self.metrics.record_error('network_verification', str(e))
                except Exception as metrics_error:
                    logger.error(f"Failed to record error in metrics: {metrics_error}")
            raise NetworkError(f"Network verification failed: {e}")

    @pytest.fixture(scope="class", autouse=True)
    async def setup_test(self, web3, config, latency_optimizer, metrics):
        """Initialize test environment with realistic mainnet conditions."""
        try:
            # Initialize class attributes
            self.web3 = web3
            self.config = config
            self.optimizer = latency_optimizer  # Ensure this is not None
            self.metrics = metrics
            self.start_time = time.time()
            self.ws_connections = []
            self.test_metrics = {}

            # Ensure metrics is initialized
            if not hasattr(self, 'metrics') or self.metrics is None:
                metrics_dir = os.path.join(os.getcwd(), 'tmp')
                os.makedirs(metrics_dir, exist_ok=True)
                self.metrics = MetricsCollector(metrics_dir=metrics_dir)
                await self.metrics.start_metrics_collection()
            
            # Initialize monitoring with mainnet-like settings
            await self.optimizer.start_mempool_monitoring(
                max_pending_tx=5000,  # Handle high tx volume
                block_time=12  # Ethereum block time
            )
            
            try:
                # Try to set up WebSocket connections if available
                if hasattr(self.optimizer, 'ws_connections'):
                    self.ws_connections = self.optimizer.ws_connections
                else:
                    self.ws_connections = []
                    logger.warning("WebSocket connections not available, continuing with HTTP only")
                
                # Simulate realistic mainnet conditions
                await self.optimizer.simulate_network_conditions(
                    base_fee=web3.to_wei(50, 'gwei'),  # Moderate gas price
                    block_usage=0.8,  # High block utilization
                    latency=0.05,  # Target 50ms latency
                    packet_loss=0.01  # 1% packet loss
                )
            except Exception as e:
                logger.warning(f"Error setting up WebSocket connections: {e}")
            
            # Initialize metrics monitoring
            await self.metrics.start_metrics_collection()
            
            yield
            
        except Exception as e:
            logger.error(f"Error in test setup: {e}")
            if hasattr(self, 'metrics'):
                self.metrics.record_error('test_setup', str(e))
            raise
        finally:
            # Cleanup resources
            try:
                if hasattr(self, 'metrics'):
                    self.metrics.cleanup()
                if hasattr(self, 'optimizer'):
                    self.optimizer.monitoring_active = False
                    if hasattr(self.optimizer, 'ws_connections'):
                        for ws in self.optimizer.ws_connections:
                            if hasattr(ws.provider, 'disconnect'):
                                await ws.provider.disconnect()
            except Exception as e:
                logger.error(f"Error in test cleanup: {e}")

    @pytest.mark.asyncio
    async def test_optimized_mempool_monitoring(self):
        """Test mempool monitoring with latency optimizations for mainnet conditions."""
        processed_txs = []
        blocks_monitored = 0
        latencies = []
        test_start_time = time.time()  # Local start time for this test
        
        try:
            # Verify network conditions first
            await self.verify_network_conditions()
            
            # Simulate realistic mainnet conditions
            await self.optimizer.simulate_network_conditions(
                base_fee=self.web3.to_wei(100, 'gwei'),  # High gas price scenario
                block_usage=0.95,  # Near-full blocks
                latency=0.05,  # Target 50ms latency
                packet_loss=0.02  # 2% packet loss for resilience testing
            )

            # Record initial metrics
            self.test_metrics['start_time'] = test_start_time
            self.test_metrics['initial_gas'] = self.web3.eth.gas_price
            self.test_metrics['initial_block'] = self.web3.eth.block_number
            
            # Start mempool monitoring with mainnet-optimized parameters
            await self.optimizer.start_mempool_monitoring(
                max_pending_tx=self.config['optimization']['mempool']['max_pending_tx'],
                block_time=self.config['network']['block_time']
            )
            
            if hasattr(self, 'metrics') and self.metrics is not None:
                try:
                    self.metrics.update_mempool_status(True)
                except Exception as e:
                    logger.warning(f"Failed to update mempool status: {e}")
            
            # Monitor blocks with enhanced metrics
            max_blocks = 10  # Monitor more blocks for better statistics
            timeout = time.time() + 60  # 1 minute timeout
            min_profit = int(self.config['optimization']['mempool']['min_profit_threshold'])
            retry_count = 0
            max_retries = self.config['network']['max_retries']
            
            while blocks_monitored < max_blocks and time.time() < timeout:
                try:
                    # Get and process new transactions
                    tx_start = time.time()
                    new_txs = await self.optimizer.get_new_transactions()
                    tx_latency = time.time() - tx_start
                    latencies.append(tx_latency)
                    
                    if new_txs:
                        blocks_monitored += 1
                        processed_txs.extend(new_txs)
                        
                        # Process transactions in parallel with timeout
                        async def analyze_tx(tx):
                            try:
                                tx_type = self.optimizer.classify_transaction(tx)
                                if tx_type in ['potential_mev', 'flash_loan']:
                                    profit = await self.optimizer.estimate_profit_potential(tx)
                                    if profit > min_profit:
                                        return tx_type, profit
                            except Exception as e:
                                logger.debug(f"Error analyzing tx: {e}")
                            return None, 0
                        
                        analysis_tasks = [
                            asyncio.create_task(analyze_tx(tx))
                            for tx in new_txs[:self.config['optimization']['mempool']['max_batch_size']]
                        ]
                        
                        done, pending = await asyncio.wait(
                            analysis_tasks,
                            timeout=self.config['network']['http_request_timeout']
                        )
                        
                        for task in pending:
                            task.cancel()
                        
                        results = [task.result() for task in done if not task.cancelled()]
                        
                        # Calculate MEV statistics
                        mev_txs = [(tx, profit) for (tx_type, profit), tx in zip(results, new_txs) if tx_type]
                        mev_count = len(mev_txs)
                        total_profit_potential = sum(profit for _, profit in mev_txs)
                        
                        # Record metrics if available
                        if hasattr(self, 'metrics') and self.metrics is not None:
                            try:
                                self.metrics.record_block_transactions(len(new_txs))
                                mev_ratio = mev_count / len(new_txs) if new_txs else 0
                                self.metrics.record_competition('mempool', mev_ratio)
                                self.metrics.record_latency('tx_processing', tx_latency)
                                
                                if total_profit_potential > 0:
                                    self.metrics.record_profit('potential_mev', total_profit_potential)
                            except Exception as e:
                                logger.warning(f"Failed to record metrics: {e}")
                        
                        retry_count = 0
                        
                        if blocks_monitored % 3 == 0:
                            await self.verify_network_conditions()
                    
                    sleep_time = min(
                        self.config['optimization']['latency']['max_acceptable'],
                        max(0.01, tx_latency * 0.5)
                    )
                    await asyncio.sleep(sleep_time)
                    
                except Exception as e:
                    retry_count += 1
                    if hasattr(self, 'metrics') and self.metrics is not None:
                        try:
                            self.metrics.record_error('tx_processing', str(e))
                        except Exception as metrics_error:
                            logger.error(f"Failed to record error in metrics: {metrics_error}")
                    logger.error(f"Error processing transactions: {e}")
                    
                    if retry_count >= max_retries:
                        raise RuntimeError(f"Max retries ({max_retries}) exceeded")
                    
                    await asyncio.sleep(min(1.0, 0.1 * (2 ** retry_count)))
                    continue
            
            # Calculate and verify latency statistics
            if latencies:
                avg_latency = statistics.mean(latencies)
                p95_latency = statistics.quantiles(latencies, n=20)[18]
                max_latency = max(latencies)
                
                assert avg_latency < 0.1, f"Average latency {avg_latency*1000:.2f}ms exceeds 100ms target"
                assert p95_latency < 0.15, f"95th percentile latency {p95_latency*1000:.2f}ms too high"
                assert max_latency < 0.2, f"Maximum latency {max_latency*1000:.2f}ms too high"
                
                if hasattr(self, 'metrics') and self.metrics is not None:
                    try:
                        self.metrics.record_latency('avg_mempool', avg_latency)
                        self.metrics.record_latency('p95_mempool', p95_latency)
                        self.metrics.record_latency('max_mempool', max_latency)
                    except Exception as e:
                        logger.warning(f"Failed to record latency metrics: {e}")
            
            # Verify monitoring effectiveness
            assert blocks_monitored > 0, "Should monitor at least one block"
            assert time.time() - test_start_time < 60, "Monitoring should complete within timeout"
            
        except Exception as e:
            if hasattr(self, 'metrics') and self.metrics is not None:
                try:
                    self.metrics.record_error('mempool_monitoring', str(e))
                except Exception as metrics_error:
                    logger.error(f"Failed to record error in metrics: {metrics_error}")
            raise
        finally:
            if hasattr(self, 'metrics') and self.metrics is not None:
                try:
                    self.metrics.update_mempool_status(False)
                    
                    # Record final metrics
                    end_time = time.time()
                    duration = end_time - test_start_time
                    final_gas = self.web3.eth.gas_price
                    final_block = self.web3.eth.block_number
                    
                    # Record comprehensive summary
                    summary = {
                        'duration': duration,
                        'initial_gas': self.test_metrics.get('initial_gas'),
                        'final_gas': final_gas,
                        'blocks_monitored': blocks_monitored,
                        'total_txs': len(processed_txs),
                        'blocks_processed': final_block - self.test_metrics.get('initial_block', final_block),
                        'avg_latency': statistics.mean(latencies) if latencies else None,
                        'p95_latency': statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else None,
                        'max_latency': max(latencies) if latencies else None,
                        'tx_success_rate': len([tx for tx in processed_txs if tx.get('status', 0) == 1]) / len(processed_txs) if processed_txs else 0,
                        'block_success_rate': blocks_monitored / max_blocks if max_blocks > 0 else 0,
                        'tx_per_block': len(processed_txs) / blocks_monitored if blocks_monitored > 0 else 0
                    }
                    
                    self.metrics.record_test_summary(summary)
                    
                    if latencies:
                        self.metrics.record_latency_distribution(latencies)
                        
                except Exception as e:
                    logger.error(f"Error recording final metrics: {e}")

    async def generate_test_transactions(
        self,
        count: int,
        base_fee: int,
        priority_fee: int
    ) -> List[Dict[str, Any]]:
        """Generate test transactions with realistic parameters."""
        try:
            test_txs = []
            for i in range(count):
                tx_type = random.choice(['swap', 'flash_loan', 'standard'])
                
                # Generate realistic transaction data based on type
                data = '0x'
                if tx_type == 'swap':
                    # Simulate Uniswap V2 swapExactTokensForTokens
                    data = '0x38ed1739' + ''.join(random.choices('0123456789abcdef', k=136))
                elif tx_type == 'flash_loan':
                    # Simulate Aave flash loan
                    data = '0xab9c4b5d' + ''.join(random.choices('0123456789abcdef', k=200))
                
                # Generate transaction hash using keccak
                tx_hash = Web3.keccak(text=f"{time.time()}{i}").hex()
                
                tx = {
                    'type': '0x2',
                    'chainId': 1,
                    'nonce': i,
                    'to': f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
                    'value': random.randint(0, 10**18),
                    'gas': random.randint(21000, 500000),
                    'maxFeePerGas': (base_fee + priority_fee) * 10**9,
                    'maxPriorityFeePerGas': priority_fee * 10**9,
                    'data': data,
                    'hash': tx_hash,
                    'timestamp': int(time.time())
                }
                test_txs.append(tx)
                    
            return test_txs
            
        except Exception as e:
            if hasattr(self, 'metrics') and self.metrics is not None:
                try:
                    self.metrics.record_error('tx_generation', str(e))
                except Exception as metrics_error:
                    logger.error(f"Failed to record error in metrics: {metrics_error}")
            raise

if __name__ == '__main__':
    pytest.main(['-v', 'test_latency_optimization.py'])
