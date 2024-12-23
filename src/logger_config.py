"""Logging configuration for the arbitrage bot."""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import time

# Create logs directory if it doesn't exist
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

# Configure logging
logger = logging.getLogger('arbitrage_bot')
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
console_handler.setFormatter(console_formatter)

# File handler with rotation
log_file = log_dir / f'arbitrage_bot_{int(time.time())}.log'
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(file_formatter)

# Add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Prevent logging from propagating to the root logger
logger.propagate = False

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    child_logger = logger.getChild(name)
    child_logger.setLevel(logger.level)
    return child_logger
