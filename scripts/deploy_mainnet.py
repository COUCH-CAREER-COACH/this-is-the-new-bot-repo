#!/usr/bin/env python3

import asyncio
import json
import os
import sys
import time
from decimal import Decimal
from web3 import Web3
from eth_account import Account
import argparse
import logging
from typing import Dict, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import ArbitrageBot
from src.risk_management import RiskManager
from src.monitoring import MonitoringSystem
from src.security import SecurityManager
from src.logger_config import logger

class MainnetDeployment:
    def __init__(self):
        """Initialize mainnet deployment."""
        self.setup_logging()
        self.load_config()
        self.initialize_web3()
        self.initialize_components()
        
        # Deployment state
        self.deployment_stage = 0
        self.start_time = time.time()
        self.test_transactions = []
        
    def setup_logging(self):
        """Setup deployment logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('logs/mainnet_deployment.log')
            ]
        )

    def load_config(self):
        """Load mainnet configuration."""
        try:
            with open('config/mainnet.config.json', 'r') as f:
                self.config = json.load(f)
            logger.info("Loaded mainnet configuration")
        except Exception as e:
            logger.error(f"Failed to load mainnet config: {e}")
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
            
            # Verify network
            chain_id = self.w3.eth.chain_id
            if chain_id != 1:  # Mainnet
                raise ValueError(f"Wrong network: {chain_id}. Must be connected to Mainnet")
            
            logger.info(f"Connected to Ethereum Mainnet (Chain ID: {chain_id})")
            
        except Exception as e:
            logger.error(f"Web3 initialization failed: {e}")
            sys.exit(1)

    def initialize_components(self):
        """Initialize bot components."""
        try:
            # Initialize components
            self.risk_manager = RiskManager(self.w3, self.config)
            self.monitoring = MonitoringSystem(self.w3, self.config)
            self.security = SecurityManager(self.w3, self.config)
            
            # Initialize bot
            self.bot = ArbitrageBot(
                web3=self.w3,
                flash_loan_contract_address=self.config['flash_loan']['providers']['aave']['pool_address_provider']
            )
            
            # Attach components to bot
            self.bot.risk_manager = self.risk_manager
            self.bot.monitoring = self.monitoring
            self.bot.security = self.security
            
            logger.info("Initialized all components")
            
        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            sys.exit(1)

    async def run_preflight_checks(self) -> bool:
        """Run comprehensive preflight checks."""
        try:
            logger.info("Running preflight checks...")
            
            # Check node connection and sync
            block = self.w3.eth.block_number
            node_time = self.w3.eth.get_block('latest')['timestamp']
            if abs(time.time() - node_time) > 60:
                raise ValueError("Node not properly synced")
            
            # Check account balance
            balance = self.w3.eth.get_balance(self.w3.eth.default_account)
            min_balance = Web3.to_wei(1, 'ether')  # Minimum 1 ETH
            if balance < min_balance:
                raise ValueError(f"Insufficient balance: {Web3.from_wei(balance, 'ether')} ETH")
            
            # Check gas price
            gas_price = self.w3.eth.gas_price
            max_gas = Web3.to_wei(100, 'gwei')
            if gas_price > max_gas:
                raise ValueError(f"Gas price too high: {Web3.from_wei(gas_price, 'gwei')} gwei")
            
            # Verify contract addresses
            contracts_to_check = [
                ('Aave Pool', self.config['flash_loan']['providers']['aave']['pool_address_provider']),
                ('Uniswap Router', self.config['dex']['uniswap_v2_router']),
                ('Uniswap Factory', self.config['dex']['uniswap_v2_factory'])
            ]
            
            for name, address in contracts_to_check:
                if not self.w3.eth.get_code(Web3.to_checksum_address(address)):
                    raise ValueError(f"Invalid contract: {name} at {address}")
            
            # Check system health
            health_status = await self.monitoring.run_health_check()
            if not health_status:
                raise ValueError("System health check failed")
            
            logger.info("All preflight checks passed")
            return True
            
        except Exception as e:
            logger.error(f"Preflight checks failed: {e}")
            return False

    async def run_simulation_phase(self) -> bool:
        """Run simulation phase with test transactions."""
        try:
            logger.info("Starting simulation phase...")
            
            # Monitor mempool for test opportunities
            test_duration = 600  # 10 minutes
            start_time = time.time()
            
            while time.time() - start_time < test_duration:
                # Get pending transactions
                pending_txs = await self.bot.get_pending_transactions()
                
                for tx in pending_txs:
                    # Analyze transaction
                    opportunity = await self.bot.analyze_transaction(tx)
                    if opportunity:
                        # Simulate execution without sending
                        success = await self.security._simulate_transaction(opportunity)
                        if success:
                            self.test_transactions.append({
                                'tx': tx,
                                'opportunity': opportunity,
                                'timestamp': time.time()
                            })
                
                await asyncio.sleep(1)
            
            # Analyze results
            if len(self.test_transactions) < 10:
                raise ValueError("Too few opportunities found during simulation")
            
            # Calculate theoretical profits
            total_profit = Decimal('0')
            for test in self.test_transactions:
                profit = Decimal(str(test['opportunity'].get('expected_profit', '0')))
                total_profit += profit
            
            avg_profit = total_profit / len(self.test_transactions)
            min_required = Decimal(str(self.config['strategies']['frontrun']['min_profit_wei']))
            
            if avg_profit < min_required:
                raise ValueError(f"Average profit ({avg_profit}) below minimum threshold ({min_required})")
            
            logger.info(f"Simulation successful: {len(self.test_transactions)} opportunities, avg profit: {avg_profit}")
            return True
            
        except Exception as e:
            logger.error(f"Simulation phase failed: {e}")
            return False

    async def run_gradual_rollout(self) -> bool:
        """Execute gradual rollout with increasing position sizes."""
        try:
            logger.info("Starting gradual rollout...")
            
            # Define rollout stages
            stages = [
                {'duration': 3600, 'max_position': '0.1'},  # 1 hour, 0.1 ETH max
                {'duration': 7200, 'max_position': '0.5'},  # 2 hours, 0.5 ETH max
                {'duration': 14400, 'max_position': '1.0'}  # 4 hours, 1.0 ETH max
            ]
            
            for i, stage in enumerate(stages, 1):
                logger.info(f"Starting rollout stage {i}")
                
                # Update position limits
                self.config['risk_management']['max_position_size_usd'] = str(
                    float(stage['max_position']) * float(self.get_eth_price())
                )
                
                # Run bot for stage duration
                start_time = time.time()
                success = await self.run_bot_with_timeout(stage['duration'])
                
                if not success:
                    raise ValueError(f"Rollout stage {i} failed")
                
                # Analyze stage performance
                metrics = self.monitoring.get_current_metrics()
                performance = metrics['performance_metrics']
                
                if performance['win_rate'] < 0.7:  # Require 70% win rate
                    raise ValueError(f"Insufficient win rate in stage {i}: {performance['win_rate']}")
                
                logger.info(f"Successfully completed rollout stage {i}")
                
            logger.info("Gradual rollout completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Gradual rollout failed: {e}")
            return False

    async def run_bot_with_timeout(self, duration: int) -> bool:
        """Run bot for specified duration with monitoring."""
        try:
            # Start bot
            await self.bot.start()
            
            start_time = time.time()
            while time.time() - start_time < duration:
                # Run health checks
                health_status = await self.monitoring.run_health_check()
                if not health_status:
                    raise ValueError("Health check failed during bot operation")
                
                # Check risk metrics
                if self.risk_manager.should_emergency_shutdown():
                    raise ValueError("Risk management triggered emergency shutdown")
                
                # Update gas metrics
                await self.monitoring.update_gas_metrics()
                
                # Generate periodic reports
                await self.monitoring.generate_profit_report()
                
                await asyncio.sleep(60)  # Check every minute
            
            # Stop bot
            await self.bot.stop()
            return True
            
        except Exception as e:
            logger.error(f"Bot operation failed: {e}")
            await self.bot.stop()
            return False

    def get_eth_price(self) -> float:
        """Get current ETH price in USD."""
        try:
            # Use Chainlink ETH/USD price feed
            price_feed_address = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
            abi = [{"inputs":[],"name":"latestAnswer","outputs":[{"internalType":"int256","name":"","type":"int256"}],"stateMutability":"view","type":"function"}]
            contract = self.w3.eth.contract(address=price_feed_address, abi=abi)
            price = contract.functions.latestAnswer().call()
            return float(price) / 1e8  # Chainlink uses 8 decimals
        except Exception as e:
            logger.error(f"Failed to get ETH price: {e}")
            return 2000.0  # Fallback price

async def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description='Mainnet Deployment Script')
    parser.add_argument('--force', action='store_true', help='Force deployment without confirmation')
    args = parser.parse_args()
    
    deployment = MainnetDeployment()
    
    if not args.force:
        confirm = input("WARNING: This will deploy the bot to mainnet. Are you sure? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Deployment cancelled")
            return
    
    # Run deployment stages
    stages = [
        ('Preflight Checks', deployment.run_preflight_checks),
        ('Simulation Phase', deployment.run_simulation_phase),
        ('Gradual Rollout', deployment.run_gradual_rollout)
    ]
    
    for stage_name, stage_func in stages:
        logger.info(f"Starting {stage_name}")
        success = await stage_func()
        
        if not success:
            logger.error(f"{stage_name} failed. Aborting deployment.")
            return
        
        logger.info(f"{stage_name} completed successfully")
    
    logger.info("Mainnet deployment completed successfully")

if __name__ == "__main__":
    asyncio.run(main())
