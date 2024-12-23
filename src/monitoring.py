import logging
import time
from typing import Dict, Optional, List
from decimal import Decimal
import json
import os
import asyncio
from web3 import Web3
import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class MonitoringSystem:
    def __init__(self, web3: Web3, config: Dict):
        """Initialize monitoring system."""
        self.w3 = web3
        self.config = config['monitoring']
        self.security = config['security']
        
        # Initialize metrics storage
        self.metrics = {
            'system_health': {},
            'performance_metrics': {},
            'gas_metrics': [],
            'block_metrics': [],
            'trade_metrics': [],
            'alerts': []
        }
        
        # Initialize state
        self.last_health_check = time.time()
        self.last_gas_update = time.time()
        self.last_profit_report = time.time()
        self.last_block = 0
        
        # Create metrics directory
        os.makedirs('metrics', exist_ok=True)
        
        logger.info("Monitoring system initialized")

    async def run_health_check(self) -> bool:
        """Run comprehensive system health check."""
        try:
            now = time.time()
            if now - self.last_health_check < self.config['health_check_interval']:
                return True
                
            self.last_health_check = now
            health_status = {
                'timestamp': now,
                'web3_connected': False,
                'node_synced': False,
                'gas_price_healthy': False,
                'balance_sufficient': False,
                'block_delay_acceptable': False
            }
            
            # Check Web3 connection
            try:
                current_block = self.w3.eth.block_number
                health_status['web3_connected'] = True
                
                # Check node sync status
                node_time = self.w3.eth.get_block('latest')['timestamp']
                if abs(now - node_time) < 60:  # Within 1 minute
                    health_status['node_synced'] = True
                
                # Check block delay
                if self.last_block > 0:
                    block_delay = current_block - self.last_block
                    health_status['block_delay_acceptable'] = block_delay <= self.config['max_block_delay']
                self.last_block = current_block
                
            except Exception as e:
                logger.error(f"Web3 health check failed: {e}")
                
            # Check gas price
            try:
                gas_price = self.w3.eth.gas_price
                health_status['gas_price_healthy'] = gas_price <= int(self.config['alert_thresholds']['high_gas'])
            except Exception as e:
                logger.error(f"Gas price check failed: {e}")
                
            # Check ETH balance
            try:
                balance = self.w3.eth.get_balance(self.w3.eth.default_account)
                min_balance = int(self.config['alert_thresholds']['low_balance'])
                health_status['balance_sufficient'] = balance > min_balance
            except Exception as e:
                logger.error(f"Balance check failed: {e}")
            
            # Update metrics
            self.metrics['system_health'] = health_status
            
            # Save metrics
            self._save_metrics()
            
            # Return overall health status
            return all(health_status.values())
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def update_gas_metrics(self):
        """Update gas price metrics."""
        try:
            now = time.time()
            if now - self.last_gas_update < self.config['gas_price_update_interval']:
                return
                
            self.last_gas_update = now
            
            # Get current gas prices
            gas_price = self.w3.eth.gas_price
            block = self.w3.eth.block_number
            
            # Store gas metric
            gas_metric = {
                'timestamp': now,
                'block': block,
                'gas_price': gas_price,
                'gas_price_gwei': self.w3.from_wei(gas_price, 'gwei')
            }
            
            # Add to metrics history
            self.metrics['gas_metrics'].append(gas_metric)
            
            # Keep last 1000 metrics
            if len(self.metrics['gas_metrics']) > 1000:
                self.metrics['gas_metrics'] = self.metrics['gas_metrics'][-1000:]
            
            # Check for alerts
            if gas_price > int(self.config['alert_thresholds']['high_gas']):
                self._add_alert('HIGH_GAS_PRICE', f"Gas price above threshold: {gas_price}")
                
        except Exception as e:
            logger.error(f"Error updating gas metrics: {e}")

    def record_trade_metrics(self, trade: Dict):
        """Record metrics for a completed trade."""
        try:
            trade_metric = {
                'timestamp': time.time(),
                'trade_id': trade.get('id'),
                'strategy': trade.get('strategy'),
                'profit_loss': str(trade.get('profit_loss', '0')),
                'gas_used': trade.get('gas_used', 0),
                'gas_price': trade.get('gas_price', 0),
                'execution_time': trade.get('execution_time', 0),
                'slippage': trade.get('slippage', 0)
            }
            
            # Add to metrics history
            self.metrics['trade_metrics'].append(trade_metric)
            
            # Keep last 1000 trades
            if len(self.metrics['trade_metrics']) > 1000:
                self.metrics['trade_metrics'] = self.metrics['trade_metrics'][-1000:]
            
            # Check for alerts
            if trade.get('slippage', 0) > self.config['alert_thresholds']['high_slippage']:
                self._add_alert('HIGH_SLIPPAGE', f"High slippage in trade {trade.get('id')}: {trade.get('slippage')}")
                
            # Update performance metrics
            self._update_performance_metrics()
            
        except Exception as e:
            logger.error(f"Error recording trade metrics: {e}")

    def _update_performance_metrics(self):
        """Update overall performance metrics."""
        try:
            if not self.metrics['trade_metrics']:
                return
                
            # Convert trade metrics to DataFrame for analysis
            df = pd.DataFrame(self.metrics['trade_metrics'])
            df['profit_loss'] = df['profit_loss'].astype(float)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            
            # Calculate performance metrics
            total_trades = len(df)
            profitable_trades = len(df[df['profit_loss'] > 0])
            total_profit = df['profit_loss'].sum()
            win_rate = profitable_trades / total_trades if total_trades > 0 else 0
            
            # Calculate Sharpe ratio (if enough data)
            if len(df) > 1:
                returns = df['profit_loss'].pct_change().dropna()
                sharpe_ratio = np.sqrt(365) * (returns.mean() / returns.std()) if returns.std() != 0 else 0
            else:
                sharpe_ratio = 0
            
            # Update metrics
            self.metrics['performance_metrics'] = {
                'total_trades': total_trades,
                'profitable_trades': profitable_trades,
                'total_profit': str(total_profit),
                'win_rate': win_rate,
                'sharpe_ratio': sharpe_ratio,
                'last_updated': time.time()
            }
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")

    async def generate_profit_report(self) -> Optional[Dict]:
        """Generate periodic profit and performance report."""
        try:
            now = time.time()
            if now - self.last_profit_report < self.config['profit_report_interval']:
                return None
                
            self.last_profit_report = now
            
            if not self.metrics['trade_metrics']:
                return None
                
            # Convert trade metrics to DataFrame
            df = pd.DataFrame(self.metrics['trade_metrics'])
            df['profit_loss'] = df['profit_loss'].astype(float)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            
            # Calculate time-based metrics
            last_24h = df[df['timestamp'] > datetime.now() - timedelta(days=1)]
            last_7d = df[df['timestamp'] > datetime.now() - timedelta(days=7)]
            
            report = {
                'timestamp': now,
                'last_24h': {
                    'total_trades': len(last_24h),
                    'total_profit': str(last_24h['profit_loss'].sum()),
                    'avg_profit_per_trade': str(last_24h['profit_loss'].mean() if len(last_24h) > 0 else 0),
                    'win_rate': len(last_24h[last_24h['profit_loss'] > 0]) / len(last_24h) if len(last_24h) > 0 else 0
                },
                'last_7d': {
                    'total_trades': len(last_7d),
                    'total_profit': str(last_7d['profit_loss'].sum()),
                    'avg_profit_per_trade': str(last_7d['profit_loss'].mean() if len(last_7d) > 0 else 0),
                    'win_rate': len(last_7d[last_7d['profit_loss'] > 0]) / len(last_7d) if len(last_7d) > 0 else 0
                },
                'all_time': {
                    'total_trades': len(df),
                    'total_profit': str(df['profit_loss'].sum()),
                    'avg_profit_per_trade': str(df['profit_loss'].mean() if len(df) > 0 else 0),
                    'win_rate': len(df[df['profit_loss'] > 0]) / len(df) if len(df) > 0 else 0
                }
            }
            
            # Save report
            self._save_report(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating profit report: {e}")
            return None

    def _add_alert(self, alert_type: str, message: str):
        """Add a new alert to the monitoring system."""
        try:
            alert = {
                'timestamp': time.time(),
                'type': alert_type,
                'message': message
            }
            
            self.metrics['alerts'].append(alert)
            
            # Keep last 100 alerts
            if len(self.metrics['alerts']) > 100:
                self.metrics['alerts'] = self.metrics['alerts'][-100:]
            
            # Log alert
            logger.warning(f"Alert: {alert_type} - {message}")
            
        except Exception as e:
            logger.error(f"Error adding alert: {e}")

    def _save_metrics(self):
        """Save current metrics to disk."""
        try:
            with open('metrics/current_metrics.json', 'w') as f:
                json.dump(self.metrics, f)
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")

    def _save_report(self, report: Dict):
        """Save profit report to disk."""
        try:
            timestamp = datetime.fromtimestamp(report['timestamp']).strftime('%Y%m%d_%H%M%S')
            with open(f'metrics/report_{timestamp}.json', 'w') as f:
                json.dump(report, f)
        except Exception as e:
            logger.error(f"Error saving report: {e}")

    def get_current_metrics(self) -> Dict:
        """Get current monitoring metrics."""
        return self.metrics

    def get_alerts(self) -> List[Dict]:
        """Get current alerts."""
        return self.metrics['alerts']

    def clear_alerts(self):
        """Clear all current alerts."""
        self.metrics['alerts'] = []
        self._save_metrics()
