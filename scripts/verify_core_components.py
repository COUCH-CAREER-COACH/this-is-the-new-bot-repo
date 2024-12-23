"""Verify core components of the arbitrage bot."""
import asyncio
import json
import logging
from pathlib import Path
from web3 import Web3
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("core-verify")

class CoreVerification:
    def __init__(self):
        # Initialize with local node
        self.w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
        self.config = None
        self.contracts = {}
        
    def verify_node_connection(self):
        """Verify connection to Ethereum node."""
        try:
            if not self.w3.is_connected():
                logger.error("❌ Not connected to Ethereum node")
                return False
            
            block = self.w3.eth.get_block('latest')
            logger.info(f"✅ Connected to node at block {block['number']}")
            return True
        except Exception as e:
            logger.error(f"❌ Node connection error: {e}")
            return False

    def verify_config(self):
        """Verify configuration is valid."""
        try:
            # Load config
            config_path = Path('config/test.local.config.json')
            if not config_path.exists():
                logger.error("❌ Config file not found")
                return False
                
            with open(config_path) as f:
                self.config = json.load(f)

            # Check required DEX addresses
            required = [
                ('Uniswap Router', self.config['dex']['uniswap_v2_router']),
                ('Sushiswap Router', self.config['dex']['sushiswap_router']),
                ('WETH', self.config['dex']['test_tokens']['WETH']),
                ('USDC', self.config['dex']['test_tokens']['USDC'])
            ]

            for name, addr in required:
                if not Web3.is_address(addr):
                    logger.error(f"❌ Invalid {name} address: {addr}")
                    return False
                logger.info(f"✅ Valid {name} address: {addr}")

            return True
        except Exception as e:
            logger.error(f"❌ Config verification error: {e}")
            return False

    def verify_contract_abis(self):
        """Verify all required contract ABIs exist."""
        try:
            required_abis = [
                ('Router', 'contracts/interfaces/IUniswapV2Router02.json'),
                ('Factory', 'contracts/interfaces/IUniswapV2Factory.json'),
                ('Pair', 'contracts/interfaces/IUniswapV2Pair.json')
            ]

            for name, path in required_abis:
                if not Path(path).exists():
                    logger.error(f"❌ {name} ABI file not found: {path}")
                    return False
                    
                with open(path) as f:
                    abi = json.load(f)
                    if 'abi' not in abi:
                        logger.error(f"❌ Invalid {name} ABI format")
                        return False
                    self.contracts[name.lower()] = abi['abi']
                    logger.info(f"✅ Loaded {name} ABI")

            return True
        except Exception as e:
            logger.error(f"❌ ABI verification error: {e}")
            return False

    async def verify_dex_access(self):
        """Verify we can access DEX contracts."""
        try:
            # Initialize router contracts
            uni_router = self.w3.eth.contract(
                address=self.config['dex']['uniswap_v2_router'],
                abi=self.contracts['router']
            )
            sushi_router = self.w3.eth.contract(
                address=self.config['dex']['sushiswap_router'],
                abi=self.contracts['router']
            )

            # Get factory addresses
            uni_factory = uni_router.functions.factory().call()
            sushi_factory = sushi_router.functions.factory().call()

            logger.info(f"✅ Uniswap factory: {uni_factory}")
            logger.info(f"✅ Sushiswap factory: {sushi_factory}")

            # Try getting a price quote
            amount_in = self.w3.to_wei(1, 'ether')
            path = [
                self.config['dex']['test_tokens']['WETH'],
                self.config['dex']['test_tokens']['USDC']
            ]

            # Get quotes from both DEXes
            uni_quote = uni_router.functions.getAmountsOut(amount_in, path).call()
            sushi_quote = sushi_router.functions.getAmountsOut(amount_in, path).call()

            logger.info(f"✅ Uniswap quote: {uni_quote[1]} USDC for 1 ETH")
            logger.info(f"✅ Sushiswap quote: {sushi_quote[1]} USDC for 1 ETH")

            # Calculate price difference
            uni_price = Decimal(uni_quote[1]) / Decimal(amount_in)
            sushi_price = Decimal(sushi_quote[1]) / Decimal(amount_in)
            diff = abs(uni_price - sushi_price) / min(uni_price, sushi_price)

            logger.info(f"✅ Price difference: {diff * 100:.2f}%")
            return True

        except Exception as e:
            logger.error(f"❌ DEX access error: {e}")
            return False

async def main():
    verifier = CoreVerification()
    
    # Run verifications
    if not verifier.verify_node_connection():
        return
        
    if not verifier.verify_config():
        return
        
    if not verifier.verify_contract_abis():
        return
        
    if not await verifier.verify_dex_access():
        return
        
    logger.info("✅ All core components verified successfully")

if __name__ == "__main__":
    asyncio.run(main())
