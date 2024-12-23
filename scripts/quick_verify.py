"""Quick verification of core arbitrage functionality."""
import asyncio
from web3 import Web3
import json
from decimal import Decimal
import logging
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("arbitrage-verify")

class QuickArbitrageTest:
    def __init__(self, w3: Web3, config: dict):
        self.w3 = w3
        self.config = config
        self.uniswap_router = w3.to_checksum_address(config['dex']['uniswap_v2_router'])
        self.sushiswap_router = w3.to_checksum_address(config['dex']['sushiswap_router'])
        self.weth = w3.to_checksum_address(config['dex']['test_tokens']['WETH'])
        self.usdc = w3.to_checksum_address(config['dex']['test_tokens']['USDC'])

    async def verify_dex_connection(self):
        """Verify we can connect to DEXes."""
        try:
            # Load router ABI
            with open('contracts/interfaces/IUniswapV2Router02.json', 'r') as f:
                router_abi = json.load(f)['abi']

            # Initialize router contracts
            uni_router = self.w3.eth.contract(address=self.uniswap_router, abi=router_abi)
            sushi_router = self.w3.eth.contract(address=self.sushiswap_router, abi=router_abi)

            # Check factory addresses
            uni_factory = uni_router.functions.factory().call()
            sushi_factory = sushi_router.functions.factory().call()

            logger.info(f"Uniswap factory: {uni_factory}")
            logger.info(f"Sushiswap factory: {sushi_factory}")

            return True
        except Exception as e:
            logger.error(f"Error verifying DEX connection: {e}")
            return False

    async def check_price_difference(self):
        """Check price difference between Uniswap and Sushiswap."""
        try:
            # Load router ABI
            with open('contracts/interfaces/IUniswapV2Router02.json', 'r') as f:
                router_abi = json.load(f)['abi']

            # Initialize router contracts
            uni_router = self.w3.eth.contract(address=self.uniswap_router, abi=router_abi)
            sushi_router = self.w3.eth.contract(address=self.sushiswap_router, abi=router_abi)

            # Amount to test (1 ETH)
            amount_in = self.w3.to_wei(1, 'ether')

            # Get amounts out from both DEXes
            uni_amount = uni_router.functions.getAmountsOut(
                amount_in,
                [self.weth, self.usdc]
            ).call()

            sushi_amount = sushi_router.functions.getAmountsOut(
                amount_in,
                [self.weth, self.usdc]
            ).call()

            # Calculate price difference
            uni_price = uni_amount[1] / amount_in
            sushi_price = sushi_amount[1] / amount_in
            price_diff = abs(uni_price - sushi_price) / min(uni_price, sushi_price)

            logger.info(f"Uniswap price: {uni_price} USDC/ETH")
            logger.info(f"Sushiswap price: {sushi_price} USDC/ETH")
            logger.info(f"Price difference: {price_diff * 100:.2f}%")

            return price_diff > 0.01  # Return True if price diff > 1%
        except Exception as e:
            logger.error(f"Error checking price difference: {e}")
            return False

async def main():
    # Load config
    with open('config/test.local.config.json', 'r') as f:
        config = json.load(f)

    # Initialize Web3 with local Ganache
    w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
    
    if not w3.is_connected():
        # Try Infura as fallback
        logger.info("Failed to connect to local node, trying Infura...")
        w3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/9aa3d95b3bc440fa88ea12eaa4456161'))
        
        if not w3.is_connected():
            logger.error("Failed to connect to Ethereum node")
            return

    logger.info("Connected to Ethereum node")
    logger.info(f"Current block: {w3.eth.block_number}")
    
    # Initialize test
    tester = QuickArbitrageTest(w3, config)

    # Run verifications
    logger.info("Verifying DEX connections...")
    if await tester.verify_dex_connection():
        logger.info("✅ DEX connections verified")
    else:
        logger.error("❌ DEX connection failed")
        return

    logger.info("Checking price differences...")
    if await tester.check_price_difference():
        logger.info("✅ Found price difference > 1%")
    else:
        logger.info("❌ No significant price difference found")

if __name__ == "__main__":
    asyncio.run(main())
