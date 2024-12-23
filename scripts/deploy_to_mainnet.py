"""Deploy optimized arbitrage bot to mainnet with comprehensive safety checks."""
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import subprocess
import time
import yaml
from web3 import Web3
from web3.exceptions import Web3Exception
from eth_account import Account
import aiohttp
from typing import Dict, Any, List, Optional

# Import verification scripts
from scripts.verify_security import verify_security_settings
from scripts.mainnet_readiness_check import MainnetReadinessChecker
from scripts.deploy_optimizations import OptimizationDeployer
from src.metrics_collector import MetricsCollector

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

class MainnetDeployer:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.load_config()
        self.setup_web3()
        self.metrics = MetricsCollector(port=8080)
        self.deployment_steps = []
        self.deployment_state = {}
        self.start_time = time.time()

    def load_config(self):
        """Load and validate configuration."""
        try:
            # Load JSON config
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            
            # Load YAML alert rules
            with open('rules/alerts.yml', 'r') as f:
                self.alert_rules = yaml.safe_load(f)
            
            # Validate required configuration
            required_keys = ['network', 'strategies', 'monitoring']
            for key in required_keys:
                if key not in self.config:
                    raise ValueError(f"Missing required configuration key: {key}")
                    
            # Load environment variables
            self.load_env_variables()
            
        except Exception as e:
            logger.error(f"Configuration error: {e}")
            raise

    def load_env_variables(self):
        """Load and verify required environment variables."""
        required_vars = [
            'MAINNET_RPC_URL',
            'ETHERSCAN_API_KEY',
            'GRAFANA_API_KEY',
            'DISCORD_WEBHOOK_URL'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")

    def setup_web3(self):
        """Initialize Web3 with fallback providers."""
        providers = [
            self.config['network']['http_provider'],
            os.getenv('BACKUP_RPC_URL'),
            'https://eth-mainnet.alchemyapi.io/v2/' + os.getenv('ALCHEMY_API_KEY', '')
        ]
        
        for provider in filter(None, providers):
            try:
                self.w3 = Web3(Web3.HTTPProvider(provider))
                if self.w3.is_connected():
                    logger.info(f"Connected to Ethereum node at {provider}")
                    return
            except Exception as e:
                logger.warning(f"Failed to connect to {provider}: {e}")
                
        raise ConnectionError("Failed to connect to any Ethereum node")

    async def verify_deployment_prerequisites(self) -> bool:
        """Verify all deployment prerequisites are met."""
        try:
            logger.info("Verifying deployment prerequisites...")
            
            # Check deployment lock
            if await self.check_deployment_lock():
                raise ValueError("Another deployment is in progress")
            
            # Create deployment lock
            await self.create_deployment_lock()
            
            # Verify network conditions
            if not await self.verify_network_conditions():
                raise ValueError("Network conditions not suitable for deployment")
            
            # Verify contract states
            if not await self.verify_contract_states():
                raise ValueError("Contract verification failed")
            
            # Verify wallet balances
            if not await self.verify_wallet_balances():
                raise ValueError("Insufficient wallet balances")
            
            self.deployment_steps.append("✅ Prerequisites verified")
            return True
            
        except Exception as e:
            logger.error(f"Prerequisite verification failed: {e}")
            return False

    async def run_pre_deployment_checks(self) -> bool:
        """Run comprehensive pre-deployment verification."""
        try:
            logger.info("Running pre-deployment checks...")
            
            # Security audit
            logger.info("Running security audit...")
            if not await verify_security_settings():
                raise ValueError("Security audit failed")
            self.deployment_steps.append("✅ Security audit passed")
            
            # Mainnet readiness
            logger.info("Checking mainnet readiness...")
            readiness_checker = MainnetReadinessChecker(self.config_path)
            if not await readiness_checker.check_all():
                raise ValueError("Mainnet readiness check failed")
            self.deployment_steps.append("✅ Mainnet readiness verified")
            
            # Run optimization tests
            logger.info("Running optimization tests...")
            if not await self.run_optimization_tests():
                raise ValueError("Optimization tests failed")
            self.deployment_steps.append("✅ Optimization tests passed")
            
            # Verify monitoring setup
            logger.info("Verifying monitoring setup...")
            if not await self.verify_monitoring_setup():
                raise ValueError("Monitoring setup verification failed")
            self.deployment_steps.append("✅ Monitoring setup verified")
            
            return True
            
        except Exception as e:
            logger.error(f"Pre-deployment checks failed: {e}")
            return False

    async def deploy_monitoring_infrastructure(self) -> bool:
        """Deploy and configure monitoring infrastructure."""
        try:
            logger.info("Deploying monitoring infrastructure...")
            
            # Deploy Prometheus
            if not await self.deploy_prometheus():
                raise ValueError("Prometheus deployment failed")
            
            # Deploy Grafana
            if not await self.deploy_grafana():
                raise ValueError("Grafana deployment failed")
            
            # Configure alerts
            if not await self.configure_alerts():
                raise ValueError("Alert configuration failed")
            
            # Verify metrics collection
            if not await self.verify_metrics_collection():
                raise ValueError("Metrics collection verification failed")
            
            self.deployment_steps.append("✅ Monitoring infrastructure deployed")
            return True
            
        except Exception as e:
            logger.error(f"Monitoring deployment failed: {e}")
            return False

    async def deploy_optimized_strategies(self) -> bool:
        """Deploy optimized trading strategies."""
        try:
            logger.info("Deploying optimized strategies...")
            
            deployer = OptimizationDeployer(self.config_path)
            
            # Deploy in sequence with verification
            deployment_sequence = [
                ('gas_optimization', deployer.deploy_gas_optimization),
                ('latency_optimization', deployer.deploy_latency_optimization),
                ('position_optimization', deployer.deploy_position_optimization),
                ('risk_management', deployer.deploy_risk_management)
            ]
            
            for name, deploy_func in deployment_sequence:
                logger.info(f"Deploying {name}...")
                if not await deploy_func():
                    raise ValueError(f"{name} deployment failed")
                
                # Verify deployment
                if not await self.verify_deployment(name):
                    raise ValueError(f"{name} verification failed")
                
                self.deployment_steps.append(f"✅ {name} deployed")
                
                # Update deployment state
                self.deployment_state[name] = {
                    'status': 'deployed',
                    'timestamp': int(time.time()),
                    'verification': 'passed'
                }
            
            return True
            
        except Exception as e:
            logger.error(f"Strategy deployment failed: {e}")
            return False

    def generate_deployment_report(self) -> Path:
        """Generate comprehensive deployment report."""
        report_path = Path('reports/mainnet_deployment.md')
        report_path.parent.mkdir(exist_ok=True)
        
        try:
            with open(report_path, 'w') as f:
                f.write("# Mainnet Deployment Report\n\n")
                
                # Deployment Overview
                f.write("## Deployment Overview\n\n")
                f.write(f"- Start Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.start_time))}\n")
                f.write(f"- End Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"- Duration: {int(time.time() - self.start_time)} seconds\n\n")
                
                # Deployment Steps
                f.write("## Deployment Steps\n\n")
                for step in self.deployment_steps:
                    f.write(f"- {step}\n")
                f.write("\n")
                
                # Component Status
                f.write("## Component Status\n\n")
                for component, state in self.deployment_state.items():
                    f.write(f"### {component}\n")
                    f.write(f"- Status: {state['status']}\n")
                    f.write(f"- Deployed: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(state['timestamp']))}\n")
                    f.write(f"- Verification: {state['verification']}\n\n")
                
                # Next Steps
                f.write("## Next Steps\n\n")
                if len(self.deployment_steps) == len(self.expected_steps):
                    f.write("✅ Deployment successful! Next steps:\n\n")
                    f.write("1. Monitor system performance in Grafana\n")
                    f.write("2. Start with minimal position sizes\n")
                    f.write("3. Gradually increase positions based on performance\n")
                    f.write("4. Review metrics and adjust parameters as needed\n")
                else:
                    f.write("❌ Deployment incomplete. Required actions:\n\n")
                    f.write("1. Review deployment logs\n")
                    f.write("2. Address failed steps\n")
                    f.write("3. Re-run deployment process\n")
            
            return report_path
            
        except Exception as e:
            logger.error(f"Failed to generate deployment report: {e}")
            raise

async def main():
    """Main deployment function."""
    try:
        deployer = MainnetDeployer('config/mainnet.config.json')
        
        # Pre-deployment checks
        if not await deployer.run_pre_deployment_checks():
            logger.error("Pre-deployment checks failed. Aborting deployment.")
            sys.exit(1)
        
        # Deploy monitoring
        if not await deployer.deploy_monitoring_infrastructure():
            logger.error("Monitoring setup failed. Aborting deployment.")
            sys.exit(1)
        
        # Deploy optimizations
        if not await deployer.deploy_optimized_strategies():
            logger.error("Optimization deployment failed. Aborting deployment.")
            sys.exit(1)
        
        # Generate deployment report
        report_path = deployer.generate_deployment_report()
        logger.info(f"Deployment report generated: {report_path}")
        
        # Final verification
        if len(deployer.deployment_steps) == len(deployer.expected_steps):
            logger.info("🎉 Deployment completed successfully!")
            sys.exit(0)
        else:
            logger.error("Deployment incomplete. Please review logs.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
