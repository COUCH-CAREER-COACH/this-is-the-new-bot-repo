"""Deploy optimized strategies to mainnet with comprehensive safety checks."""
import asyncio
import json
import logging
from web3 import Web3
from web3.exceptions import Web3Exception
from decimal import Decimal
import time
from pathlib import Path
import sys
import os
from typing import Dict, Any, List, Tuple
import aiohttp

from src.optimizations import GasOptimizer, LatencyOptimizer, PositionOptimizer, RiskManager
from src.metrics_collector import MetricsCollector
from src.exceptions import (
    GasEstimationError,
    ContractError,
    ProfitabilityError,
    InsufficientLiquidityError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('deployment.log')
    ]
)
logger = logging.getLogger(__name__)

class OptimizationDeployer:
    def __init__(self, config_path: str):
        self.load_config(config_path)
        self.setup_web3()
        self.metrics = MetricsCollector(port=8080)
        self.initialize_optimizers()
        self.deployment_state = self.load_deployment_state()

    def load_config(self, config_path: str):
        """Load and validate configuration."""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            
            required_keys = [
                'network', 'strategies', 'monitoring', 'flash_loan',
                'dex', 'test_tokens'
            ]
            for key in required_keys:
                if key not in self.config:
                    raise ValueError(f"Missing required configuration key: {key}")
            
            # Validate strategy-specific configurations
            for strategy in ['arbitrage', 'jit', 'sandwich']:
                if strategy not in self.config['strategies']:
                    raise ValueError(f"Missing configuration for {strategy} strategy")
                    
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    def setup_web3(self):
        """Initialize Web3 connections with fallback nodes."""
        providers = [
            self.config['network']['http_provider'],
            self.config.get('network', {}).get('fallback_provider'),
            os.getenv('BACKUP_RPC_URL')
        ]
        
        for provider in filter(None, providers):
            try:
                self.w3 = Web3(Web3.HTTPProvider(provider))
                if self.w3.is_connected():
                    logger.info(f"Connected to Ethereum node at {provider}")
                    
                    # Setup WebSocket connection for real-time data
                    ws_provider = provider.replace('http', 'ws')
                    self.ws_w3 = Web3(Web3.WebsocketProvider(ws_provider))
                    
                    return
            except Exception as e:
                logger.warning(f"Failed to connect to {provider}: {e}")
                
        raise ConnectionError("Failed to connect to any Ethereum node")

    def initialize_optimizers(self):
        """Initialize optimization components."""
        try:
            self.gas_optimizer = GasOptimizer(self.w3, self.config)
            self.latency_optimizer = LatencyOptimizer(self.w3, self.ws_w3, self.config)
            self.position_optimizer = PositionOptimizer(self.w3, self.config)
            self.risk_manager = RiskManager(self.w3, self.config)
        except Exception as e:
            logger.error(f"Failed to initialize optimizers: {e}")
            raise

    def load_deployment_state(self) -> Dict[str, Any]:
        """Load existing deployment state or initialize new one."""
        state_path = Path('deployment_state.json')
        if state_path.exists():
            try:
                with open(state_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load deployment state: {e}")
        
        return {
            'timestamp': int(time.time()),
            'state': {
                'gas_optimization': False,
                'latency_optimization': False,
                'position_optimization': False,
                'risk_management': False
            },
            'metrics': {},
            'health_checks': {}
        }

    async def verify_contract_deployment(self) -> bool:
        """Verify all required contracts are deployed and accessible."""
        try:
            contracts_to_verify = [
                ('UniswapV2Router', self.config['dex']['uniswap_v2_router']),
                ('SushiSwapRouter', self.config['dex']['sushiswap_router']),
                ('FlashLoan', self.config['flash_loan']['providers']['aave']['pool_address'])
            ]
            
            for name, address in contracts_to_verify:
                # Verify contract exists
                code = await self.w3.eth.get_code(address)
                if code == '0x':
                    logger.error(f"{name} contract not found at {address}")
                    return False
                
                # Verify contract is verified on Etherscan
                if not await self.verify_etherscan_contract(address):
                    logger.warning(f"{name} contract not verified on Etherscan")
            
            return True
            
        except Exception as e:
            logger.error(f"Contract verification failed: {e}")
            return False

    async def verify_etherscan_contract(self, address: str) -> bool:
        """Verify contract on Etherscan."""
        try:
            etherscan_api_key = os.getenv('ETHERSCAN_API_KEY')
            if not etherscan_api_key:
                logger.warning("ETHERSCAN_API_KEY not set")
                return False
                
            async with aiohttp.ClientSession() as session:
                url = f"https://api.etherscan.io/api"
                params = {
                    'module': 'contract',
                    'action': 'getabi',
                    'address': address,
                    'apikey': etherscan_api_key
                }
                
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    return data['status'] == '1'
                    
        except Exception as e:
            logger.error(f"Etherscan verification failed: {e}")
            return False

    async def check_network_conditions(self) -> bool:
        """Comprehensive check of network conditions."""
        try:
            # Basic connection check
            if not self.w3.is_connected():
                logger.error("Not connected to Ethereum node")
                return False
            
            # Network verification
            chain_id = await self.w3.eth.chain_id
            if chain_id != 1:
                logger.error(f"Wrong network. Expected Mainnet (1), got {chain_id}")
                return False
            
            # Node sync status
            sync_status = await self.w3.eth.syncing
            if sync_status:
                logger.error("Node is still syncing")
                return False
            
            # Gas price check
            gas_price = await self.w3.eth.gas_price
            max_gas = self.config['strategies']['arbitrage']['max_gas_price_300_gwei']
            if gas_price > int(max_gas):
                logger.error(f"Gas price too high: {self.w3.from_wei(gas_price, 'gwei')} gwei")
                return False
            
            # Block time check
            latest_block = await self.w3.eth.get_block('latest')
            prev_block = await self.w3.eth.get_block(latest_block['number'] - 1)
            block_time = latest_block['timestamp'] - prev_block['timestamp']
            if block_time > 15:
                logger.warning(f"Block time higher than normal: {block_time}s")
            
            # Mempool check
            pending_tx_count = await self.w3.eth.get_block_transaction_count('pending')
            if pending_tx_count > 50000:
                logger.warning(f"High mempool load: {pending_tx_count} pending transactions")
            
            # Network peers check
            peer_count = await self.w3.net.peer_count
            if peer_count < 10:
                logger.warning(f"Low peer count: {peer_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"Network condition check failed: {e}")
            return False

    async def verify_monitoring_setup(self) -> bool:
        """Verify monitoring infrastructure is properly configured."""
        try:
            # Check Prometheus
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:9090/-/healthy') as response:
                    if response.status != 200:
                        logger.error("Prometheus health check failed")
                        return False
            
            # Check Grafana
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:3000/api/health') as response:
                    if response.status != 200:
                        logger.error("Grafana health check failed")
                        return False
            
            # Verify metrics collection
            test_metric = await self.metrics.collect_metric('arbitrage_opportunities_total')
            if test_metric is None:
                logger.error("Metrics collection test failed")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Monitoring verification failed: {e}")
            return False

    async def deploy_gas_optimization(self) -> bool:
        """Deploy gas optimization with comprehensive testing."""
        try:
            logger.info("Deploying gas optimization...")
            
            # Test gas estimation across different network conditions
            gas_prices = []
            for _ in range(5):
                gas_price = await self.gas_optimizer.estimate_optimal_gas_price('arbitrage')
                if gas_price <= 0:
                    raise ValueError("Invalid gas price estimation")
                gas_prices.append(gas_price)
                await asyncio.sleep(1)
            
            # Verify gas price stability
            gas_price_variance = max(gas_prices) - min(gas_prices)
            if gas_price_variance > self.w3.to_wei(50, 'gwei'):
                logger.warning("High gas price variance detected")
            
            # Test transaction batching
            test_txs = await self.generate_test_transactions()
            tx_hash = await self.gas_optimizer.batch_transactions(test_txs)
            if not tx_hash:
                raise ValueError("Transaction batching failed")
            
            # Wait for transaction confirmation
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash)
            if not receipt['status']:
                raise ValueError("Test transaction failed")
            
            # Record deployment metrics
            self.deployment_state['state']['gas_optimization'] = True
            self.deployment_state['metrics']['gas_optimization'] = {
                'timestamp': int(time.time()),
                'avg_gas_price': sum(gas_prices) / len(gas_prices),
                'gas_price_variance': gas_price_variance
            }
            
            logger.info("Gas optimization deployed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Gas optimization deployment failed: {e}")
            return False

    async def deploy_latency_optimization(self) -> bool:
        """Deploy latency optimization with performance verification."""
        try:
            logger.info("Deploying latency optimization...")
            
            # Start mempool monitoring
            await self.latency_optimizer.start_mempool_monitoring()
            
            # Verify WebSocket connection stability
            for _ in range(5):
                if not self.ws_w3.is_connected():
                    raise ValueError("WebSocket connection unstable")
                await asyncio.sleep(1)
            
            # Test transaction capture performance
            capture_times = []
            for _ in range(10):
                start_time = time.time()
                tx = await self.latency_optimizer.get_pending_transaction()
                if tx:
                    capture_times.append(time.time() - start_time)
            
            if capture_times:
                avg_capture_time = sum(capture_times) / len(capture_times)
                if avg_capture_time > 0.5:  # 500ms threshold
                    logger.warning(f"High transaction capture latency: {avg_capture_time:.3f}s")
            
            # Record deployment metrics
            self.deployment_state['state']['latency_optimization'] = True
            self.deployment_state['metrics']['latency_optimization'] = {
                'timestamp': int(time.time()),
                'avg_capture_time': avg_capture_time if capture_times else None,
                'captured_tx_count': len(capture_times)
            }
            
            logger.info("Latency optimization deployed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Latency optimization deployment failed: {e}")
            return False

    async def deploy_position_optimization(self) -> bool:
        """Deploy position optimization with market simulation."""
        try:
            logger.info("Deploying position optimization...")
            
            # Test position sizing across different market conditions
            test_scenarios = [
                {'volatility': 'low', 'liquidity': 'high'},
                {'volatility': 'high', 'liquidity': 'high'},
                {'volatility': 'low', 'liquidity': 'low'},
                {'volatility': 'high', 'liquidity': 'low'}
            ]
            
            results = []
            for scenario in test_scenarios:
                # Configure test pool
                test_pool = await self.get_test_pool_config(scenario)
                
                # Calculate optimal position
                position_size, metrics = await self.position_optimizer.calculate_optimal_position(
                    'arbitrage',
                    test_pool,
                    Decimal('1000.0')
                )
                
                if position_size <= 0:
                    raise ValueError(f"Invalid position size for scenario: {scenario}")
                
                results.append({
                    'scenario': scenario,
                    'position_size': position_size,
                    'metrics': metrics
                })
            
            # Verify position size consistency
            position_sizes = [r['position_size'] for r in results]
            size_variance = max(position_sizes) - min(position_sizes)
            if size_variance > self.w3.to_wei(10, 'ether'):
                logger.warning("High position size variance across scenarios")
            
            # Record deployment metrics
            self.deployment_state['state']['position_optimization'] = True
            self.deployment_state['metrics']['position_optimization'] = {
                'timestamp': int(time.time()),
                'scenarios_tested': len(results),
                'avg_position_size': sum(position_sizes) / len(position_sizes),
                'position_size_variance': size_variance
            }
            
            logger.info("Position optimization deployed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Position optimization deployment failed: {e}")
            return False

    async def deploy_risk_management(self) -> bool:
        """Deploy risk management with comprehensive safety checks."""
        try:
            logger.info("Deploying risk management...")
            
            # Test circuit breakers
            circuit_breaker_tests = [
                ('gas_price', self.test_gas_circuit_breaker),
                ('volatility', self.test_volatility_circuit_breaker),
                ('exposure', self.test_exposure_circuit_breaker),
                ('profit', self.test_profit_circuit_breaker)
            ]
            
            test_results = {}
            for name, test_func in circuit_breaker_tests:
                success = await test_func()
                test_results[name] = success
                if not success:
                    raise ValueError(f"{name} circuit breaker test failed")
            
            # Test risk limits
            await self.verify_risk_limits()
            
            # Test emergency shutdown
            if not await self.test_emergency_shutdown():
                raise ValueError("Emergency shutdown test failed")
            
            # Record deployment metrics
            self.deployment_state['state']['risk_management'] = True
            self.deployment_state['metrics']['risk_management'] = {
                'timestamp': int(time.time()),
                'circuit_breaker_tests': test_results
            }
            
            logger.info("Risk management deployed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Risk management deployment failed: {e}")
            return False

    async def verify_deployment(self) -> bool:
        """Verify complete deployment status."""
        try:
            # Check all components are deployed
            if not all(self.deployment_state['state'].values()):
                logger.error("Not all components are deployed")
                return False
            
            # Verify integration between components
            if not await self.verify_component_integration():
                return False
            
            # Run final health check
            if not await self.run_health_check():
                return False
            
            logger.info("Deployment verification successful")
            return True
            
        except Exception as e:
            logger.error(f"Deployment verification failed: {e}")
            return False

    def save_deployment_state(self):
        """Save detailed deployment state."""
        try:
            state_path = Path('deployment_state.json')
            self.deployment_state['last_updated'] = int(time.time())
            
            with open(state_path, 'w') as f:
                json.dump(self.deployment_state, f, indent=4)
            
            logger.info(f"Deployment state saved to {state_path}")
            
        except Exception as e:
            logger.error(f"Failed to save deployment state: {e}")
            raise

async def main():
    """Main deployment function with comprehensive checks."""
    try:
        # Initialize deployer
        deployer = OptimizationDeployer('config/mainnet.config.json')
        
        # Pre-deployment checks
        logger.info("Running pre-deployment checks...")
        
        checks = [
            ("Network Conditions", deployer.check_network_conditions()),
            ("Contract Verification", deployer.verify_contract_deployment()),
            ("Monitoring Setup", deployer.verify_monitoring_setup())
        ]
        
        for check_name, check_coro in checks:
            logger.info(f"Running {check_name} check...")
            if not await check_coro:
                logger.error(f"{check_name} check failed")
                return False
        
        # Deploy components
        deployments = [
            ("Gas Optimization", deployer.deploy_gas_optimization()),
            ("Latency Optimization", deployer.deploy_latency_optimization()),
            ("Position Optimization", deployer.deploy_position_optimization()),
            ("Risk Management", deployer.deploy_risk_management())
        ]
        
        for name, deploy_coro in deployments:
            logger.info(f"Deploying {name}...")
            if not await deploy_coro:
                logger.error(f"{name} deployment failed")
                return False
            logger.info(f"{name} deployed successfully")
        
        # Verify complete deployment
        if not await deployer.verify_deployment():
            logger.error("Deployment verification failed")
            return False
        
        # Save final state
        deployer.save_deployment_state()
        
        logger.info("Deployment completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
