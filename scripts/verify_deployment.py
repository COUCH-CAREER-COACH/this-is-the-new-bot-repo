"""Verify deployment readiness according to the deployment checklist."""
import asyncio
import json
import logging
from pathlib import Path
from web3 import Web3
import os
from dotenv import load_dotenv
from hexbytes import HexBytes

# Load environment variables
load_dotenv()
MAINNET_RPC_URL = os.getenv('MAINNET_RPC_URL')
if not MAINNET_RPC_URL:
    raise ValueError("MAINNET_RPC_URL environment variable is not set")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("deployment-verify")

class DeploymentVerification:
    def __init__(self):
        self.w3 = None
        self.config = None

    async def verify_environment(self):
        """Verify environment setup."""
        logger.info("1. Environment Setup")
        
        # Check Ethereum node connection
        try:
            self.w3 = Web3(Web3.HTTPProvider(MAINNET_RPC_URL))
            if not self.w3.is_connected():
                logger.error("❌ Failed to connect to Ethereum node")
                return False
            logger.info(f"✅ Connected to Ethereum node at block {self.w3.eth.block_number}")
        except Exception as e:
            logger.error(f"❌ Node connection error: {e}")
            return False

        # Check configuration
        try:
            config_path = Path('config/test.local.config.json')
            if not config_path.exists():
                logger.error("❌ Config file not found")
                return False
            
            with open(config_path) as f:
                self.config = json.load(f)
            logger.info("✅ Configuration loaded")
        except Exception as e:
            logger.error(f"❌ Config error: {e}")
            return False

        return True

    async def verify_contracts(self):
        """Verify smart contracts."""
        logger.info("\n2. Contract Verification")
        
        try:
            # Check contract files exist
            contract_files = [
                'contracts/FlashLoanArbitrage.sol',
                'contracts/interfaces/IUniswapV2Router02.json',
                'contracts/interfaces/IUniswapV2Factory.json',
                'contracts/interfaces/IUniswapV2Pair.json'
            ]
            
            for file in contract_files:
                if not Path(file).exists():
                    logger.error(f"❌ Missing contract file: {file}")
                    return False
                logger.info(f"✅ Found contract file: {file}")

            # Verify contract addresses
            addresses = {
                'Uniswap Router': self.config['dex']['uniswap_v2_router'],
                'Sushiswap Router': self.config['dex']['sushiswap_router'],
                'WETH': self.config['dex']['test_tokens']['WETH'],
                'USDC': self.config['dex']['test_tokens']['USDC']
            }
            
            for name, addr in addresses.items():
                if not Web3.is_address(addr):
                    logger.error(f"❌ Invalid {name} address: {addr}")
                    return False
                
                code = self.w3.eth.get_code(addr)
                if code == b'' or code == HexBytes('0x'):
                    logger.error(f"❌ No contract code at {name} address: {addr}")
                    return False
                    
                logger.info(f"✅ Verified {name} contract at {addr}")

            return True
            
        except Exception as e:
            logger.error(f"❌ Contract verification error: {e}")
            return False

async def main():
    verifier = DeploymentVerification()
    
    # Run verifications
    if not await verifier.verify_environment():
        return
        
    if not await verifier.verify_contracts():
        return
        
    logger.info("\n✅ All deployment checks passed successfully")

if __name__ == "__main__":
    asyncio.run(main())
