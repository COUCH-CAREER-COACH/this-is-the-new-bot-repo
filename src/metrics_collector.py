"""Metrics collection and monitoring module."""
import time
import os
import json
import socket
from typing import Dict, Any, Optional
from decimal import Decimal
from pathlib import Path
import asyncio
from prometheus_client import start_http_server, Counter, Gauge, Histogram

from .logger_config import logger

def find_free_port() -> int:
    """Find a free port to use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

class MetricsCollector:
    """Collects and exposes metrics for monitoring."""
    
    def __init__(self, port: Optional[int] = None, metrics_dir: Optional[str] = None):
        """Initialize metrics collector."""
        try:
            # Find available port if none specified
            self.port = port or find_free_port()
            
            # Start Prometheus HTTP server
            start_http_server(self.port)
            
            # Set metrics directory
            self.metrics_dir = metrics_dir or os.path.join(os.getcwd(), 'metrics')
            os.makedirs(self.metrics_dir, exist_ok=True)
            
            # Initialize Prometheus metrics
            self._init_prometheus_metrics()
            
            # Initialize internal metrics storage
            self.metrics = {
                'latency': {},
                'gas': {},
                'profit': {},
                'success_rate': {},
                'competition': {},
                'errors': {},
                'uptime': {}
            }
            
            logger.info(f"Metrics collector initialized on port {self.port}")
            
        except Exception as e:
            logger.error(f"Error initializing metrics collector: {e}")
            raise

    def _init_prometheus_metrics(self):
        """Initialize Prometheus metric collectors."""
        # Latency metrics
        self.latency_histogram = Histogram(
            'arbitrage_latency_seconds',
            'Transaction latency in seconds',
            ['operation']
        )
        
        # Gas metrics
        self.gas_price_gauge = Gauge(
            'arbitrage_gas_price_gwei',
            'Current gas price in gwei'
        )
        
        # Profit metrics
        self.profit_counter = Counter(
            'arbitrage_profit_wei',
            'Total profit in wei',
            ['strategy']
        )
        
        # Success rate metrics
        self.success_gauge = Gauge(
            'arbitrage_success_rate',
            'Success rate of operations',
            ['operation']
        )
        
        # Competition metrics
        self.competition_gauge = Gauge(
            'arbitrage_competition_level',
            'MEV competition level',
            ['type']
        )
        
        # Error metrics
        self.error_counter = Counter(
            'arbitrage_errors_total',
            'Total number of errors',
            ['type']
        )
        
        # Uptime metrics
        self.uptime_gauge = Gauge(
            'arbitrage_uptime_ratio',
            'Uptime ratio',
            ['component']
        )
        
        # Throughput metrics
        self.throughput_gauge = Gauge(
            'arbitrage_throughput',
            'Operations per second',
            ['operation']
        )

    def record_latency(self, operation: str, latency: float):
        """Record operation latency."""
        try:
            # Update Prometheus metric
            self.latency_histogram.labels(operation=operation).observe(latency)
            
            # Update internal storage
            if operation not in self.metrics['latency']:
                self.metrics['latency'][operation] = []
            self.metrics['latency'][operation].append(latency)
            
            # Write to file periodically
            if len(self.metrics['latency'][operation]) >= 100:
                self._write_metrics('latency', operation)
                
        except Exception as e:
            logger.error(f"Error recording latency: {e}")

    def update_gas_price(self, gas_price: int):
        """Update current gas price metric."""
        try:
            # Convert to gwei for readability
            gas_price_gwei = Decimal(str(gas_price)) / Decimal('1000000000')
            
            # Update Prometheus metric
            self.gas_price_gauge.set(float(gas_price_gwei))
            
            # Update internal storage
            self.metrics['gas']['current'] = gas_price
            
            # Write to file
            self._write_metrics('gas', 'price')
            
        except Exception as e:
            logger.error(f"Error updating gas price: {e}")

    def record_profit(self, strategy: str, profit: int):
        """Record profit from strategy execution."""
        try:
            # Update Prometheus metric
            self.profit_counter.labels(strategy=strategy).inc(profit)
            
            # Update internal storage
            if strategy not in self.metrics['profit']:
                self.metrics['profit'][strategy] = []
            self.metrics['profit'][strategy].append(profit)
            
            # Write to file periodically
            if len(self.metrics['profit'][strategy]) >= 10:
                self._write_metrics('profit', strategy)
                
        except Exception as e:
            logger.error(f"Error recording profit: {e}")

    def record_success_rate(self, operation: str, success_rate: float):
        """Record operation success rate."""
        try:
            # Update Prometheus metric
            self.success_gauge.labels(operation=operation).set(success_rate)
            
            # Update internal storage
            self.metrics['success_rate'][operation] = success_rate
            
            # Write to file
            self._write_metrics('success_rate', operation)
            
        except Exception as e:
            logger.error(f"Error recording success rate: {e}")

    def record_competition(self, competition_type: str, level: float):
        """Record MEV competition level."""
        try:
            # Update Prometheus metric
            self.competition_gauge.labels(type=competition_type).set(level)
            
            # Update internal storage
            self.metrics['competition'][competition_type] = level
            
            # Write to file
            self._write_metrics('competition', competition_type)
            
        except Exception as e:
            logger.error(f"Error recording competition level: {e}")

    def record_error(self, error_type: str, error_msg: str):
        """Record error occurrence."""
        try:
            # Update Prometheus metric
            self.error_counter.labels(type=error_type).inc()
            
            # Update internal storage
            if error_type not in self.metrics['errors']:
                self.metrics['errors'][error_type] = []
            self.metrics['errors'][error_type].append({
                'timestamp': time.time(),
                'message': error_msg
            })
            
            # Write to file periodically
            if len(self.metrics['errors'][error_type]) >= 10:
                self._write_metrics('errors', error_type)
                
        except Exception as e:
            logger.error(f"Error recording error: {e}")

    def record_uptime(self, component: str, uptime: float):
        """Record component uptime ratio."""
        try:
            # Update Prometheus metric
            self.uptime_gauge.labels(component=component).set(uptime)
            
            # Update internal storage
            self.metrics['uptime'][component] = uptime
            
            # Write to file
            self._write_metrics('uptime', component)
            
        except Exception as e:
            logger.error(f"Error recording uptime: {e}")

    def record_execution_time(self, operation: str, execution_time: float):
        """Record operation execution time."""
        try:
            # Use latency histogram for execution time
            self.latency_histogram.labels(operation=operation).observe(execution_time)
            
            # Update internal storage
            if operation not in self.metrics['latency']:
                self.metrics['latency'][operation] = []
            self.metrics['latency'][operation].append(execution_time)
            
            # Write to file periodically
            if len(self.metrics['latency'][operation]) >= 100:
                self._write_metrics('latency', operation)
                
        except Exception as e:
            logger.error(f"Error recording execution time: {e}")

    def record_block_transactions(self, tx_count: int):
        """Record number of transactions in block."""
        try:
            # Store in internal metrics
            if 'block_transactions' not in self.metrics:
                self.metrics['block_transactions'] = []
            self.metrics['block_transactions'].append({
                'timestamp': time.time(),
                'count': tx_count
            })
            
            # Write to file periodically
            if len(self.metrics['block_transactions']) >= 100:
                self._write_metrics('block_transactions', 'count')
                
        except Exception as e:
            logger.error(f"Error recording block transactions: {e}")

    def update_mempool_status(self, active: bool):
        """Update mempool monitoring status."""
        try:
            # Update internal storage
            self.metrics['mempool_status'] = {
                'timestamp': time.time(),
                'active': active
            }
            
            # Write to file
            self._write_metrics('mempool', 'status')
            
        except Exception as e:
            logger.error(f"Error updating mempool status: {e}")

    def record_throughput(self, operation: str, ops_per_second: float):
        """Record operation throughput."""
        try:
            # Update Prometheus metric
            self.throughput_gauge.labels(operation=operation).set(ops_per_second)
            
            # Update internal storage
            if 'throughput' not in self.metrics:
                self.metrics['throughput'] = {}
            if operation not in self.metrics['throughput']:
                self.metrics['throughput'][operation] = []
            self.metrics['throughput'][operation].append({
                'timestamp': time.time(),
                'value': ops_per_second
            })
            
            # Write to file periodically
            if len(self.metrics['throughput'][operation]) >= 100:
                self._write_metrics('throughput', operation)
                
        except Exception as e:
            logger.error(f"Error recording throughput: {e}")

    def _write_metrics(self, metric_type: str, metric_name: str):
        """Write metrics to file."""
        try:
            # Create metric file path
            file_path = os.path.join(
                self.metrics_dir,
                f"{metric_type}_{metric_name}.json"
            )
            
            # Write metrics
            with open(file_path, 'w') as f:
                json.dump(
                    self.metrics[metric_type][metric_name],
                    f,
                    indent=2
                )
                
            # Clear internal storage if list
            if isinstance(self.metrics[metric_type][metric_name], list):
                self.metrics[metric_type][metric_name] = []
                
        except Exception as e:
            logger.error(f"Error writing metrics to file: {e}")

    def cleanup(self):
        """Clean up metrics files."""
        try:
            # Write any remaining metrics
            for metric_type in self.metrics:
                for metric_name in self.metrics[metric_type]:
                    if isinstance(self.metrics[metric_type][metric_name], list) and \
                       len(self.metrics[metric_type][metric_name]) > 0:
                        self._write_metrics(metric_type, metric_name)
                        
            # Clear internal storage
            self.metrics = {
                'latency': {},
                'gas': {},
                'profit': {},
                'success_rate': {},
                'competition': {},
                'errors': {},
                'uptime': {},
                'throughput': {}
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up metrics: {e}")

    async def start_metrics_collection(self):
        """Start continuous metrics collection."""
        try:
            while True:
                # Record system metrics
                self.record_uptime('system', 1.0)  # Placeholder
                
                # Sleep for collection interval
                await asyncio.sleep(5)  # 5 second interval
                
        except Exception as e:
            logger.error(f"Error in metrics collection: {e}")
            raise

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        try:
            summary = {}
            
            # Calculate latency statistics
            for operation, latencies in self.metrics['latency'].items():
                if latencies:
                    summary[f'latency_{operation}'] = {
                        'avg': sum(latencies) / len(latencies),
                        'min': min(latencies),
                        'max': max(latencies)
                    }
                    
            # Include other metrics
            summary['gas_price'] = self.metrics['gas'].get('current', 0)
            summary['success_rates'] = self.metrics['success_rate']
            summary['competition_levels'] = self.metrics['competition']
            summary['error_counts'] = {
                error_type: len(errors)
                for error_type, errors in self.metrics['errors'].items()
            }
            summary['uptimes'] = self.metrics['uptime']
            summary['throughput'] = self.metrics.get('throughput', {})
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {}
