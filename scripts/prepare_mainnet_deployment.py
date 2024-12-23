"""Prepare for mainnet deployment"""
import asyncio
import os
import json
from web3 import Web3
from eth_utils import to_checksum_address
from typing import Dict, Any

# Constants
REQUIRED_CONFIG_KEYS = [
    'dex.uniswap_v2_router',
    'dex.uniswap_v2_factory',
    'flash_loan.preferred_provider',
    'flash_loan.providers.aave.pool_address_provider',
    'contracts.arbitrage_contract'
]

REQUIRED_FILES = [
    'contracts/FlashLoanArbitrage.sol',
    'contracts/interfaces/IUniswapV2Router02.json',
    'contracts/interfaces/IUniswapV2Factory.json',
    'contracts/interfaces/IUniswapV2Pair.json',
    'contracts/interfaces/IERC20.json'
]

async def check_config(config_path: str) -> Dict[str, Any]:
    """Check configuration file for required keys"""
    print("\nChecking configuration...")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        raise Exception(f"Configuration file not found: {config_path}")
    except json.JSONDecodeError:
        raise Exception(f"Invalid JSON in configuration file: {config_path}")
    
    # Check required keys
    missing_keys = []
    for key in REQUIRED_CONFIG_KEYS:
        parts = key.split('.')
        current = config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                missing_keys.append(key)
                break
    
    if missing_keys:
        raise Exception(f"Missing required configuration keys: {', '.join(missing_keys)}")
    
    # Validate addresses
    addresses_to_check = {
        'uniswap_v2_router': config['dex']['uniswap_v2_router'],
        'uniswap_v2_factory': config['dex']['uniswap_v2_factory'],
        'aave_pool_provider': config['flash_loan']['providers']['aave']['pool_address_provider'],
        'arbitrage_contract': config['contracts']['arbitrage_contract']
    }
    
    for name, address in addresses_to_check.items():
        try:
            to_checksum_address(address)
        except ValueError:
            raise Exception(f"Invalid Ethereum address for {name}: {address}")
    
    print("✓ Configuration validated successfully")
    return config

async def check_contract_files() -> None:
    """Check required contract files exist"""
    print("\nChecking contract files...")
    
    missing_files = []
    for file_path in REQUIRED_FILES:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        raise Exception(f"Missing required contract files: {', '.join(missing_files)}")
    
    print("✓ Contract files validated successfully")

async def check_dependencies() -> None:
    """Check required dependencies are installed"""
    print("\nChecking dependencies...")
    
    try:
        import web3
        import eth_abi
        import eth_utils
        import aiohttp
        import pytest
        import matplotlib
    except ImportError as e:
        raise Exception(f"Missing required dependency: {str(e)}")
    
    print("✓ Dependencies validated successfully")

async def check_network_connection(config: Dict[str, Any]) -> None:
    """Check connection to Ethereum network"""
    print("\nChecking network connection...")
    
    # Initialize Web3
    web3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/YOUR-PROJECT-ID'))
    
    try:
        # Check connection
        if not web3.is_connected():
            raise Exception("Failed to connect to Ethereum network")
        
        # Check block sync
        latest_block = web3.eth.block_number
        print(f"Current block number: {latest_block}")
        
        # Check contract existence
        router_address = config['dex']['uniswap_v2_router']
        code = web3.eth.get_code(router_address)
        if code == b'':
            raise Exception(f"No contract found at router address: {router_address}")
        
    except Exception as e:
        raise Exception(f"Network connection error: {str(e)}")
    
    print("✓ Network connection validated successfully")

async def check_gas_settings(config: Dict[str, Any]) -> None:
    """Check gas price settings"""
    print("\nChecking gas settings...")
    
    web3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/YOUR-PROJECT-ID'))
    
    try:
        current_gas_price = web3.eth.gas_price
        max_gas_price = Web3.to_wei(300, 'gwei')  # Example max gas price
        
        print(f"Current gas price: {Web3.from_wei(current_gas_price, 'gwei')} gwei")
        print(f"Maximum allowed: {Web3.from_wei(max_gas_price, 'gwei')} gwei")
        
        if current_gas_price > max_gas_price:
            print("WARNING: Current gas price exceeds maximum allowed")
        
    except Exception as e:
        raise Exception(f"Error checking gas settings: {str(e)}")
    
    print("✓ Gas settings validated successfully")

async def main():
    """Main function"""
    try:
        print("Starting mainnet deployment preparation...")
        
        # Check configuration
        config = await check_config('config/mainnet.config.json')
        
        # Check contract files
        await check_contract_files()
        
        # Check dependencies
        await check_dependencies()
        
        # Check network connection
        await check_network_connection(config)
        
        # Check gas settings
        await check_gas_settings(config)
        
        print("\n✓ All checks passed successfully!")
        print("\nNext steps:")
        print("1. Deploy contracts using scripts/deploy_to_mainnet.py")
        print("2. Verify contracts using scripts/verify_deployment.py")
        print("3. Run test suite using scripts/run_tests.sh")
        print("4. Monitor initial execution using scripts/monitor_mev.py")
        
    except Exception as e:
        print(f"\n❌ Error during preparation: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
