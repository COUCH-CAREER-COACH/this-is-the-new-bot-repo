#!/usr/bin/env python3
import argparse
import logging
import os
import signal
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import dotenv
from pythonjsonlogger import jsonlogger

from src.bot import ArbitrageBot
from src.utils import setup_web3_connection

# Configure logging
def setup_logging(log_level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Console handler with simple format
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with JSON format
    os.makedirs('logs', exist_ok=True)
    file_handler = RotatingFileHandler('logs/arbitrage_bot.log', maxBytes=10*1024*1024, backupCount=5)
    json_formatter = jsonlogger.JsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s')
    file_handler.setFormatter(json_formatter)
    logger.addHandler(file_handler)

    return logger

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    logging.info("Received signal for shutdown. Cleaning up...")
    # Cleanup code here if needed
    sys.exit(0)

def load_environment():
    # Load .env file if it exists
    if Path('.env').exists():
        dotenv.load_dotenv()

    required_vars = ['PRIVATE_KEY', 'RPC_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

def parse_arguments():
    parser = argparse.ArgumentParser(description='Arbitrage Bot CLI')
    parser.add_argument(
        '--config', 
        type=str,
        default='config/config.json',
        help='Path to configuration file (default: config/config.json)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set the logging level (default: INFO)'
    )
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_arguments()

    # Setup logging
    logger = setup_logging(getattr(logging, args.log_level))
    
    try:
        # Load environment variables
        load_environment()

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Initialize Web3 connection
        w3 = setup_web3_connection(os.getenv('RPC_URL'))

        # Initialize and start the bot
        bot = ArbitrageBot(
            w3=w3,
            config_path=args.config,
            private_key=os.getenv('PRIVATE_KEY')
        )
        
        logger.info("Starting arbitrage bot...")
        bot.run()

    except Exception as e:
        logger.exception(f"Fatal error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
