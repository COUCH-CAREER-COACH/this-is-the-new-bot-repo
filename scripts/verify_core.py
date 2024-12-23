"""Simple script to verify core arbitrage functionality."""
import asyncio
from web3 import Web3
import json
from decimal import Decimal
from pathlib import Path

from src.arbitrage_strategy_v2 import EnhancedArbitrageStrategy
from src.mock_flash_loan import MockFlashLoan
from src.logger_config import logger

async def main():
    # Load config
    with open('config/test.local.config.json', 'r') as f:
        config = json.load(f)

    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
    
    # Initialize mock flash loan
    flash_loan = MockFlashLoan(w3, config)
    
    # Initialize strategy
    strategy = EnhancedArbitrageStrategy(w3, config)
    strategy.flash_loan = flash_loan  # Override with mock flash loan

    # Create test transaction
    test_tx = {
        'hash': '0x' + '00' * 32,
        'to': config['dex']['uniswap_v2_router'],
        'value': w3.to_wei(1, 'ether'),
        'gasPrice': w3.to_wei(50, 'gwei'),
        'input': '0x38ed1739'  # swapExactTokensForTokens
    }

    try:
        # Analyze opportunity
        logger.info("Analyzing test transaction...")
        opportunity = await strategy.analyze_transaction(test_tx)
        
        if opportunity:
            logger.info(f"Found opportunity:")
            logger.info(f"- Amount: {Web3.from_wei(opportunity['amount'], 'ether')} ETH")
            logger.info(f"- Expected profit: {Web3.from_wei(opportunity['profit'], 'ether')} ETH")
            logger.info(f"- Gas cost: {Web3.from_wei(opportunity['gas_price'] * opportunity['gas_estimate'], 'ether')} ETH")
            
            # Execute opportunity
            logger.info("Executing opportunity...")
            success = await strategy.execute_opportunity(opportunity)
            logger.info(f"Execution {'successful' if success else 'failed'}")
            
        else:
            logger.info("No profitable opportunity found")
            
    except Exception as e:
        logger.error(f"Error testing strategy: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
