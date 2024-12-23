import logging
from decimal import Decimal
from typing import Dict, Optional
from web3 import Web3
from web3.contract import Contract
import time
import json
import os

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, web3: Web3, config: Dict):
        """Initialize risk management system."""
        self.w3 = web3
        self.config = config['risk_management']
        self.monitoring = config['monitoring']
        
        # Initialize state
        self.daily_loss = Decimal('0')
        self.daily_trades = 0
        self.failed_trades = 0
        self.last_reset = time.time()
        self.positions = {}
        self.trade_history = []
        
        # Load state if exists
        self._load_state()
        
        # Initialize circuit breaker state
        self.circuit_breaker = {
            'triggered': False,
            'last_price': {},
            'last_volume': {},
            'last_check': time.time()
        }
        
        logger.info("Risk management system initialized")

    def _load_state(self):
        """Load previous state from disk."""
        try:
            if os.path.exists('data/risk_state.json'):
                with open('data/risk_state.json', 'r') as f:
                    state = json.load(f)
                    self.daily_loss = Decimal(str(state.get('daily_loss', '0')))
                    self.daily_trades = state.get('daily_trades', 0)
                    self.failed_trades = state.get('failed_trades', 0)
                    self.last_reset = state.get('last_reset', time.time())
                    self.positions = state.get('positions', {})
                    self.trade_history = state.get('trade_history', [])
        except Exception as e:
            logger.error(f"Error loading risk state: {e}")

    def _save_state(self):
        """Save current state to disk."""
        try:
            os.makedirs('data', exist_ok=True)
            state = {
                'daily_loss': str(self.daily_loss),
                'daily_trades': self.daily_trades,
                'failed_trades': self.failed_trades,
                'last_reset': self.last_reset,
                'positions': self.positions,
                'trade_history': self.trade_history
            }
            with open('data/risk_state.json', 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Error saving risk state: {e}")

    def check_circuit_breaker(self, token_address: str, current_price: Decimal, current_volume: Decimal) -> bool:
        """Check if circuit breaker should be triggered."""
        try:
            cb_config = self.config['circuit_breaker']
            now = time.time()
            
            # Initialize price/volume tracking if needed
            if token_address not in self.circuit_breaker['last_price']:
                self.circuit_breaker['last_price'][token_address] = current_price
                self.circuit_breaker['last_volume'][token_address] = current_volume
                return False
            
            # Check time window
            if now - self.circuit_breaker['last_check'] > cb_config['time_window']:
                # Reset if outside time window
                self.circuit_breaker['last_price'][token_address] = current_price
                self.circuit_breaker['last_volume'][token_address] = current_volume
                self.circuit_breaker['last_check'] = now
                return False
            
            # Calculate price deviation
            price_change = abs(current_price - self.circuit_breaker['last_price'][token_address]) / self.circuit_breaker['last_price'][token_address]
            
            # Calculate volume change
            volume_multiplier = current_volume / self.circuit_breaker['last_volume'][token_address]
            
            # Check if circuit breaker should trigger
            if (price_change > cb_config['price_deviation'] or 
                volume_multiplier > cb_config['volume_multiplier']):
                logger.warning(
                    f"Circuit breaker triggered for {token_address}:\n"
                    f"Price change: {price_change}\n"
                    f"Volume multiplier: {volume_multiplier}"
                )
                self.circuit_breaker['triggered'] = True
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in circuit breaker check: {e}")
            return True  # Fail safe - trigger breaker on error

    def validate_trade(self, trade: Dict) -> bool:
        """Validate if a trade meets risk management criteria."""
        try:
            # Reset daily counters if needed
            self._check_daily_reset()
            
            # Check if circuit breaker is triggered
            if self.circuit_breaker['triggered']:
                logger.warning("Trade rejected - circuit breaker active")
                return False
            
            # Check daily loss limit
            if self.daily_loss >= Decimal(str(self.config['max_daily_loss'])):
                logger.warning("Trade rejected - daily loss limit reached")
                return False
            
            # Check daily trade limit
            strategy = trade.get('strategy', 'unknown')
            if strategy in self.config['strategies']:
                max_daily = self.config['strategies'][strategy]['max_daily_trades']
                if self.daily_trades >= max_daily:
                    logger.warning(f"Trade rejected - daily trade limit reached for {strategy}")
                    return False
            
            # Check position size
            position_size = Decimal(str(trade.get('amount', '0')))
            if position_size > Decimal(str(self.config['max_position_size_usd'])):
                logger.warning("Trade rejected - position size too large")
                return False
            
            # Check health factor
            if trade.get('health_factor', 0) < self.config['min_health_factor']:
                logger.warning("Trade rejected - health factor too low")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating trade: {e}")
            return False

    def record_trade_result(self, trade: Dict, success: bool, profit_loss: Decimal):
        """Record the result of a trade execution."""
        try:
            # Update counters
            if not success:
                self.failed_trades += 1
            
            self.daily_trades += 1
            
            # Update daily P&L
            if profit_loss < 0:
                self.daily_loss += abs(profit_loss)
            
            # Record trade history
            trade_record = {
                'timestamp': time.time(),
                'trade_id': trade.get('id'),
                'strategy': trade.get('strategy'),
                'success': success,
                'profit_loss': str(profit_loss),
                'gas_used': trade.get('gas_used'),
                'error': trade.get('error')
            }
            self.trade_history.append(trade_record)
            
            # Trim history if needed
            if len(self.trade_history) > 1000:
                self.trade_history = self.trade_history[-1000:]
            
            # Save state
            self._save_state()
            
            # Log trade result
            logger.info(
                f"Trade recorded:\n"
                f"Success: {success}\n"
                f"P&L: {profit_loss}\n"
                f"Daily loss: {self.daily_loss}\n"
                f"Daily trades: {self.daily_trades}"
            )
            
        except Exception as e:
            logger.error(f"Error recording trade result: {e}")

    def _check_daily_reset(self):
        """Reset daily counters if needed."""
        now = time.time()
        if now - self.last_reset >= 86400:  # 24 hours
            self.daily_loss = Decimal('0')
            self.daily_trades = 0
            self.failed_trades = 0
            self.last_reset = now
            self._save_state()
            logger.info("Daily counters reset")

    def get_position_exposure(self, token_address: str) -> Decimal:
        """Get current position exposure for a token."""
        return Decimal(str(self.positions.get(token_address, '0')))

    def update_position(self, token_address: str, amount: Decimal):
        """Update position tracking for a token."""
        current = self.get_position_exposure(token_address)
        self.positions[token_address] = str(current + amount)
        self._save_state()

    def check_drawdown(self) -> bool:
        """Check if max drawdown has been exceeded."""
        try:
            if not self.trade_history:
                return False
            
            # Calculate high water mark
            high_water_mark = Decimal('0')
            current_value = Decimal('0')
            
            for trade in self.trade_history:
                pl = Decimal(trade['profit_loss'])
                current_value += pl
                high_water_mark = max(high_water_mark, current_value)
            
            if high_water_mark > 0:
                drawdown = (high_water_mark - current_value) / high_water_mark
                return drawdown > self.config['max_drawdown']
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking drawdown: {e}")
            return True  # Fail safe

    def should_emergency_shutdown(self) -> bool:
        """Check if emergency shutdown should be triggered."""
        try:
            # Check consecutive failures
            if self.failed_trades >= self.monitoring['alert_thresholds']['failed_trades']:
                logger.critical("Emergency shutdown - too many failed trades")
                return True
            
            # Check daily loss threshold
            if self.daily_loss >= Decimal(str(self.config['emergency_shutdown_threshold'])):
                logger.critical("Emergency shutdown - daily loss threshold exceeded")
                return True
            
            # Check drawdown
            if self.check_drawdown():
                logger.critical("Emergency shutdown - max drawdown exceeded")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in emergency shutdown check: {e}")
            return True  # Fail safe

    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics for monitoring."""
        return {
            'daily_loss': str(self.daily_loss),
            'daily_trades': self.daily_trades,
            'failed_trades': self.failed_trades,
            'circuit_breaker_status': self.circuit_breaker['triggered'],
            'positions': self.positions,
            'trade_history_length': len(self.trade_history)
        }
