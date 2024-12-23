#!/usr/bin/env python3
"""Enhanced MEV bot entry point with improved logging and error handling."""
import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
from web3 import Web3

from src.bot_new import EnhancedArbitrageBot
from src.logger_config import logger
from src.utils import setup_web3

async def main():
    """Main entry point for the enhanced MEV bot."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Validate required environment variables
        required_vars = ['PROVIDER_URL', 'PRIVATE_KEY', 'FLASH_LOAN_CONTRACT']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            sys.exit(1)
            
        # Initialize Web3
        web3 = setup_web3()
        if not web3.is_connected():
            logger.error("Failed to connect to Web3 provider")
            sys.exit(1)
            
        # Get network info (fixed the async issue)
        network_id = web3.eth.chain_id
        network = "Mainnet" if network_id == 1 else "Sepolia" if network_id == 11155111 else f"Unknown ({network_id})"
        
        logger.info(
            f"\n{'='*50}"
            f"\nStarting Enhanced MEV Bot"
            f"\nNetwork: {network}"
            f"\nProvider: {os.getenv('PROVIDER_URL')}"
            f"\nFlash Loan Contract: {os.getenv('FLASH_LOAN_CONTRACT')}"
            f"\n{'='*50}"
        )
        
        # Initialize and start bot
        bot = EnhancedArbitrageBot(
            web3,
            os.getenv('FLASH_LOAN_CONTRACT')
        )
        
        await bot.start()
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await bot.stop()
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Configure uvloop for better performance
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown complete")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)
