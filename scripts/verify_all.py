"""Comprehensive verification of arbitrage bot functionality."""
import asyncio
from web3 import Web3
import json
from decimal import Decimal
import logging
import os
import subprocess
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("arbitrage-verify")

class ArbitrageVerification:
    def __init__(self):
        self.w3 = None
        self.config = None
        self.contracts = {}

    async def start_ganache(self):
        """Start Ganache with proper configuration."""
        try:
            # Kill any existing Ganache process
            subprocess.run(['pkill', '-f', 'ganache'], capture_output=True)
            
            # Start Ganache with mainnet fork
            logger.info("Starting Ganache...")
            cmd = [
                'ganache',
                '--fork.url=https://eth-mainnet.g.alchemy.com/v2/demo',
                '--fork.blockNumber=17000000',
                '--miner.defaultGasPrice=20000000000',
                '--chain.chainId=1337',
                '--server.ws=true',
                '--wallet.totalAccounts=10',
                '--server.port=8545'
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for Ganache to start
            for _ in range(30):  # 30 second timeout
                try:
                    w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
                    if w3.is_connected():
                        logger.info("✅ Ganache started successfully")
                        self.w3 = w3
                        return True
                except:
                    await asyncio.sleep(1)
                    
            raise Exception("Timeout waiting for Ganache to start")
            
        except Exception as e:
            logger.error(f"Failed to start Ganache: {e}")
            return False

    async def load_config(self):
        """Load and validate configuration."""
        try:
            # Load config
            config_path = Path('config/test.local.config.json')
            if not config_path.exists():
                raise FileNotFoundError("Config file not found")
                
            with open(config_path, 'r') as f:
                self.config = json.load(f)
                
            # Validate required fields
            required_fields = [
                'dex.uniswap_v2_router',
                'dex.sushiswap_router',
                'dex.test_tokens.WETH',
                'dex.test_tokens.USDC'
            ]
            
            for field in required_fields:
                parts = field.split('.')
                value = self.config
                for part in parts:
                    value = value.get(part)
                if not value:
                    raise ValueError(f"Missing required config field: {field}")
                    
            logger.info("✅ Configuration loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False

    async def verify_contracts(self):
        """Verify all required contracts are accessible."""
        try:
            # Load ABIs
            contract_files = {
                'router': 'contracts/interfaces/IUniswapV2Router02.json',
                'factory': 'contracts/interfaces/IUniswapV2Factory.json',
                'pair': 'contracts/interfaces/IUniswapV2Pair.json'
            }
            
            for name, path in contract_files.items():
                if not Path(path).exists():
                    raise FileNotFoundError(f"Contract ABI file not found: {path}")
                    
                with open(path, 'r') as f:
                    self.contracts[name] = json.load(f)['abi']
                    
            # Verify contract connections
            uni_router = self.w3.eth.contract(
                address=self.config['dex']['uniswap_v2_router'],
                abi=self.contracts['router']
            )
            
            sushi_router = self.w3.eth.contract(
                address=self.config['dex']['sushiswap_router'],
                abi=self.contracts['router']
            )
            
            # Verify factory addresses
            uni_factory = uni_router.functions.factory().call()
            sushi_factory = sushi_router.functions.factory().call()
            
            logger.info(f"✅ Uniswap factory verified: {uni_factory}")
            logger.info(f"✅ Sushiswap factory verified: {sushi_factory}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify contracts: {e}")
            return False

    async def check_price_feeds(self):
        """Verify price feeds are working."""
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
            
            # Test amounts
            amounts = [
                self.w3.to_wei(1, 'ether'),
                self.w3.to_wei(5, 'ether'),
                self.w3.to_wei(10, 'ether')
            ]
            
            for amount in amounts:
                # Get prices from both DEXes
                uni_out = uni_router.functions.getAmountsOut(
                    amount,
                    [
                        self.config['dex']['test_tokens']['WETH'],
                        self.config['dex']['test_tokens']['USDC']
                    ]
                ).call()
                
                sushi_out = sushi_router.functions.getAmountsOut(
                    amount,
                    [
                        self.config['dex']['test_tokens']['WETH'],
                        self.config['dex']['test_tokens']['USDC']
                    ]
                ).call()
                
                # Calculate price difference
                uni_price = uni_out[1] / amount
                sushi_price = sushi_out[1] / amount
                diff = abs(uni_price - sushi_price) / min(uni_price, sushi_price)
                
                logger.info(f"Price check for {self.w3.from_wei(amount, 'ether')} ETH:")
                logger.info(f"- Uniswap: {uni_price:.2f} USDC/ETH")
                logger.info(f"- Sushiswap: {sushi_price:.2f} USDC/ETH")
                logger.info(f"- Difference: {diff*100:.2f}%")
                
            logger.info("✅ Price feeds verified")
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify price feeds: {e}")
            return False

async def main():
    verifier = ArbitrageVerification()
    
    # Start Ganache
    if not await verifier.start_ganache():
        return
        
    # Load config
    if not await verifier.load_config():
        return
        
    # Verify contracts
    if not await verifier.verify_contracts():
        return
        
    # Check price feeds
    if not await verifier.check_price_feeds():
        return
        
    logger.info("✅ All verifications passed successfully")

if __name__ == "__main__":
    asyncio.run(main())
