#!/usr/bin/env python3

import os
import sys
import json
import asyncio
import logging
from web3 import Web3
from eth_account import Account
import argparse
from decimal import Decimal
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.security import SecurityManager
from src.monitoring import MonitoringSystem
from src.logger_config import logger

class EmergencyShutdown:
    def __init__(self):
        """Initialize emergency shutdown system."""
        self.setup_logging()
        self.load_config()
        self.initialize_web3()
        self.initialize_components()

    def setup_logging(self):
        """Setup emergency logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('logs/emergency_shutdown.log')
            ]
        )

    def load_config(self):
        """Load configuration."""
        try:
            with open('config/mainnet.config.json', 'r') as f:
                self.config = json.load(f)
            logger.info("Loaded configuration")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)

    def initialize_web3(self):
        """Initialize Web3 connection."""
        try:
            rpc_url = os.getenv('MAINNET_RPC_URL')
            if not rpc_url:
                raise ValueError("MAINNET_RPC_URL environment variable not set")
            
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not self.w3.is_connected():
                raise ConnectionError("Failed to connect to Ethereum node")
            
            # Load account
            private_key = os.getenv('PRIVATE_KEY')
            if not private_key:
                raise ValueError("PRIVATE_KEY environment variable not set")
            
            account = Account.from_key(private_key)
            self.w3.eth.default_account = account.address
            
            logger.info("Web3 initialized")
            
        except Exception as e:
            logger.error(f"Web3 initialization failed: {e}")
            sys.exit(1)

    def initialize_components(self):
        """Initialize necessary components."""
        try:
            self.security = SecurityManager(self.w3, self.config)
            self.monitoring = MonitoringSystem(self.w3, self.config)
            logger.info("Components initialized")
        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            sys.exit(1)

    async def revoke_approvals(self):
        """Revoke all token approvals."""
        try:
            logger.info("Revoking token approvals...")
            
            # Load token addresses from config
            tokens = self.config.get('strategies', {}).get('frontrun', {}).get('whitelist_tokens', [])
            
            # Add common tokens if not in whitelist
            common_tokens = [
                "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
                "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
                "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
                "0xdAC17F958D2ee523a2206206994597C13D831ec7"   # USDT
            ]
            tokens.extend([t for t in common_tokens if t not in tokens])
            
            # Spender addresses to revoke
            spenders = [
                self.config['dex']['uniswap_v2_router'],
                self.config['dex'].get('sushiswap_router'),
                self.config['flash_loan']['providers']['aave']['pool_address_provider']
            ]
            spenders = [s for s in spenders if s]  # Remove None values
            
            # Revoke all approvals
            for token in tokens:
                for spender in spenders:
                    try:
                        await self.security._revoke_token_approval(
                            self.w3.eth.contract(
                                address=Web3.to_checksum_address(token),
                                abi=self.security._get_erc20_abi()
                            ),
                            spender
                        )
                        logger.info(f"Revoked approval for token {token} spender {spender}")
                    except Exception as e:
                        logger.error(f"Failed to revoke approval for token {token} spender {spender}: {e}")
            
            logger.info("Completed revoking approvals")
            
        except Exception as e:
            logger.error(f"Error revoking approvals: {e}")

    async def withdraw_funds(self):
        """Withdraw funds to safe address."""
        try:
            logger.info("Withdrawing funds...")
            
            # Get safe address from config or env
            safe_address = os.getenv('SAFE_ADDRESS')
            if not safe_address:
                raise ValueError("SAFE_ADDRESS environment variable not set")
            
            # Check ETH balance
            balance = self.w3.eth.get_balance(self.w3.eth.default_account)
            if balance > 0:
                # Keep some ETH for gas
                gas_reserve = Web3.to_wei(0.1, 'ether')
                if balance > gas_reserve:
                    # Estimate gas for transfer
                    gas_price = self.w3.eth.gas_price
                    gas_limit = 21000  # Standard ETH transfer
                    gas_cost = gas_price * gas_limit
                    
                    # Calculate amount to send
                    amount = balance - gas_cost - gas_reserve
                    
                    if amount > 0:
                        # Send ETH
                        tx = {
                            'to': Web3.to_checksum_address(safe_address),
                            'value': amount,
                            'gas': gas_limit,
                            'gasPrice': gas_price,
                            'nonce': self.w3.eth.get_transaction_count(self.w3.eth.default_account)
                        }
                        
                        signed_tx = self.w3.eth.account.sign_transaction(
                            tx,
                            private_key=os.getenv('PRIVATE_KEY')
                        )
                        
                        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                        logger.info(f"Sent {Web3.from_wei(amount, 'ether')} ETH to safe address. TX: {tx_hash.hex()}")
            
            # Withdraw tokens
            tokens = self.config.get('strategies', {}).get('frontrun', {}).get('whitelist_tokens', [])
            for token in tokens:
                try:
                    token_contract = self.w3.eth.contract(
                        address=Web3.to_checksum_address(token),
                        abi=self.security._get_erc20_abi()
                    )
                    
                    balance = token_contract.functions.balanceOf(self.w3.eth.default_account).call()
                    if balance > 0:
                        # Transfer tokens
                        tx = token_contract.functions.transfer(
                            Web3.to_checksum_address(safe_address),
                            balance
                        ).build_transaction({
                            'from': self.w3.eth.default_account,
                            'gas': 100000,
                            'gasPrice': self.w3.eth.gas_price,
                            'nonce': self.w3.eth.get_transaction_count(self.w3.eth.default_account)
                        })
                        
                        signed_tx = self.w3.eth.account.sign_transaction(
                            tx,
                            private_key=os.getenv('PRIVATE_KEY')
                        )
                        
                        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                        logger.info(f"Sent {balance} of token {token} to safe address. TX: {tx_hash.hex()}")
                        
                except Exception as e:
                    logger.error(f"Failed to withdraw token {token}: {e}")
            
            logger.info("Completed withdrawing funds")
            
        except Exception as e:
            logger.error(f"Error withdrawing funds: {e}")

    async def save_state(self):
        """Save current state and metrics."""
        try:
            logger.info("Saving state...")
            
            # Get current metrics
            metrics = self.monitoring.get_current_metrics()
            
            # Save to file
            timestamp = int(time.time())
            filename = f'data/emergency_shutdown_state_{timestamp}.json'
            os.makedirs('data', exist_ok=True)
            
            with open(filename, 'w') as f:
                json.dump({
                    'timestamp': timestamp,
                    'metrics': metrics,
                    'alerts': self.monitoring.get_alerts()
                }, f)
            
            logger.info(f"State saved to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    async def notify_team(self):
        """Send notifications about emergency shutdown."""
        try:
            logger.info("Sending notifications...")
            
            # Log to monitoring system
            self.monitoring._add_alert(
                'EMERGENCY_SHUTDOWN',
                'Emergency shutdown procedure executed'
            )
            
            # Additional notification methods could be added here
            # (Discord, Telegram, Email, etc.)
            
            logger.info("Notifications sent")
            
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")

async def main():
    """Main emergency shutdown function."""
    parser = argparse.ArgumentParser(description='Emergency Shutdown Script')
    parser.add_argument('--force', action='store_true', help='Force shutdown without confirmation')
    args = parser.parse_args()
    
    shutdown = EmergencyShutdown()
    
    if not args.force:
        confirm = input("WARNING: This will execute emergency shutdown. Are you sure? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Shutdown cancelled")
            return
    
    # Execute shutdown sequence
    logger.info("Starting emergency shutdown sequence")
    
    try:
        # Save state first
        await shutdown.save_state()
        
        # Revoke approvals
        await shutdown.revoke_approvals()
        
        # Withdraw funds
        await shutdown.withdraw_funds()
        
        # Send notifications
        await shutdown.notify_team()
        
        logger.info("Emergency shutdown completed successfully")
        
    except Exception as e:
        logger.critical(f"Emergency shutdown failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
