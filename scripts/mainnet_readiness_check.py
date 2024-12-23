"""Mainnet deployment readiness checker."""
import asyncio
import json
import logging
from web3 import Web3
from pathlib import Path
import sys
import subprocess
import requests
import yaml
from decimal import Decimal
import os
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mainnet_readiness.log')
    ]
)
logger = logging.getLogger(__name__)

class MainnetReadinessChecker:
    def __init__(self, config_path: str):
        self.load_config(config_path)
        self.w3 = Web3(Web3.HTTPProvider(self.config['network']['http_provider']))
        self.checks_passed = 0
        self.checks_failed = 0
        self.issues = []
        self.warnings = []

    def load_config(self, config_path: str):
        """Load and validate configuration."""
        try:
            # Load JSON config
            with open(config_path, 'r') as f:
                self.config = json.load(f)

            # Load YAML alert rules
            with open('rules/alerts.yml', 'r') as f:
                self.alert_rules = yaml.safe_load(f)

            # Validate configuration
            required_sections = ['network', 'strategies', 'monitoring']
            for section in required_sections:
                if section not in self.config:
                    raise ValueError(f"Missing required config section: {section}")

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    async def check_node_connection(self) -> bool:
        """Check Ethereum node connection and sync status."""
        try:
            logger.info("Checking node connection...")
            
            if not self.w3.is_connected():
                self.issues.append("❌ Not connected to Ethereum node")
                self.checks_failed += 1
                return False
            
            # Check sync status
            sync_status = await self.w3.eth.syncing
            if sync_status:
                self.issues.append("❌ Node is still syncing")
                self.checks_failed += 1
                return False
            
            # Check chain ID
            chain_id = await self.w3.eth.chain_id
            if chain_id != 1:
                self.issues.append(f"❌ Wrong network (Chain ID: {chain_id})")
                self.checks_failed += 1
                return False
            
            self.checks_passed += 1
            return True
            
        except Exception as e:
            self.issues.append(f"❌ Node connection error: {str(e)}")
            self.checks_failed += 1
            return False

    async def check_contract_deployments(self) -> bool:
        """Verify all required contracts are deployed and accessible."""
        try:
            logger.info("Checking contract deployments...")
            contracts = [
                ('Uniswap Router', self.config['dex']['uniswap_v2_router']),
                ('Sushiswap Router', self.config['dex']['sushiswap_router']),
                ('Flash Loan Provider', self.config['flash_loan']['providers']['aave']['pool_address'])
            ]
            
            for name, address in contracts:
                # Check address format
                if not self.w3.is_address(address):
                    self.issues.append(f"❌ Invalid {name} address format")
                    self.checks_failed += 1
                    return False
                
                # Check contract code exists
                code = await self.w3.eth.get_code(address)
                if code == b'' or code == '0x':
                    self.issues.append(f"❌ No contract code at {name} address")
                    self.checks_failed += 1
                    return False
            
            self.checks_passed += 1
            return True
            
        except Exception as e:
            self.issues.append(f"❌ Contract verification error: {str(e)}")
            self.checks_failed += 1
            return False

    async def check_wallet_balance(self) -> bool:
        """Check if trading wallet has sufficient balance."""
        try:
            logger.info("Checking wallet balance...")
            account = self.w3.eth.default_account
            
            # Check ETH balance
            eth_balance = await self.w3.eth.get_balance(account)
            min_eth = self.w3.to_wei(1, 'ether')  # Minimum 1 ETH required
            
            if eth_balance < min_eth:
                self.issues.append(f"❌ Insufficient ETH balance: {self.w3.from_wei(eth_balance, 'ether')} ETH")
                self.checks_failed += 1
                return False
            
            self.checks_passed += 1
            return True
            
        except Exception as e:
            self.issues.append(f"❌ Balance check error: {str(e)}")
            self.checks_failed += 1
            return False

    async def check_gas_prices(self) -> bool:
        """Check current gas prices are within acceptable range."""
        try:
            logger.info("Checking gas prices...")
            gas_price = await self.w3.eth.gas_price
            max_gas = int(self.config['strategies']['arbitrage']['max_gas_price_300_gwei'])
            
            if gas_price > max_gas:
                self.issues.append(f"❌ Gas price too high: {self.w3.from_wei(gas_price, 'gwei')} GWEI")
                self.checks_failed += 1
                return False
            
            self.checks_passed += 1
            return True
            
        except Exception as e:
            self.issues.append(f"❌ Gas price check error: {str(e)}")
            self.checks_failed += 1
            return False

    def check_test_coverage(self) -> bool:
        """Check test coverage meets minimum requirements."""
        try:
            logger.info("Checking test coverage...")
            
            # Run pytest with coverage
            result = subprocess.run(
                ['pytest', '--cov=src', '--cov-report=term-missing'],
                capture_output=True,
                text=True
            )
            
            # Parse coverage percentage
            for line in result.stdout.split('\n'):
                if 'TOTAL' in line:
                    coverage = int(line.split()[-1].rstrip('%'))
                    if coverage < 90:
                        self.issues.append(f"❌ Insufficient test coverage: {coverage}%")
                        self.checks_failed += 1
                        return False
                    break
            
            self.checks_passed += 1
            return True
            
        except Exception as e:
            self.issues.append(f"❌ Test coverage check error: {str(e)}")
            self.checks_failed += 1
            return False

    def check_monitoring_setup(self) -> bool:
        """Verify monitoring and alerting systems are configured."""
        try:
            logger.info("Checking monitoring setup...")
            
            # Check Prometheus
            prom_response = requests.get(f"http://localhost:{self.config['monitoring']['prometheus_port']}/-/healthy")
            if prom_response.status_code != 200:
                self.issues.append("❌ Prometheus not running")
                self.checks_failed += 1
                return False
            
            # Check Grafana
            grafana_response = requests.get(f"http://localhost:{self.config['monitoring']['grafana_port']}/api/health")
            if grafana_response.status_code != 200:
                self.issues.append("❌ Grafana not running")
                self.checks_failed += 1
                return False

            # Verify alert rules are properly configured
            if not self.verify_alert_rules():
                self.issues.append("❌ Alert rules misconfigured")
                self.checks_failed += 1
                return False
            
            self.checks_passed += 1
            return True
            
        except Exception as e:
            self.issues.append(f"❌ Monitoring check error: {str(e)}")
            self.checks_failed += 1
            return False

    def verify_alert_rules(self) -> bool:
        """Verify alert rules configuration."""
        try:
            required_alerts = [
                'HighGasPrice',
                'LowProfitability',
                'NoOpportunities',
                'HighFailureRate',
                'FlashLoanErrors'
            ]

            # Check if all required alerts are configured
            configured_alerts = set()
            for group in self.alert_rules.get('groups', []):
                for rule in group.get('rules', []):
                    configured_alerts.add(rule.get('alert'))

            missing_alerts = set(required_alerts) - configured_alerts
            if missing_alerts:
                self.warnings.append(f"Missing alert rules: {', '.join(missing_alerts)}")
                return False

            return True

        except Exception as e:
            logger.error(f"Alert rules verification failed: {e}")
            return False

    def generate_report(self) -> str:
        """Generate deployment readiness report."""
        report_path = Path('reports/mainnet_readiness.md')
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w') as f:
            f.write("# Mainnet Deployment Readiness Report\n\n")
            
            # Summary
            f.write("## Summary\n")
            total_checks = self.checks_passed + self.checks_failed
            f.write(f"- Total Checks: {total_checks}\n")
            f.write(f"- Checks Passed: {self.checks_passed}\n")
            f.write(f"- Checks Failed: {self.checks_failed}\n")
            f.write(f"- Success Rate: {(self.checks_passed/total_checks)*100:.1f}%\n\n")
            
            # Issues
            if self.issues:
                f.write("## Issues Found\n")
                for issue in self.issues:
                    f.write(f"- {issue}\n")
                f.write("\n")

            # Warnings
            if self.warnings:
                f.write("## Warnings\n")
                for warning in self.warnings:
                    f.write(f"- ⚠️ {warning}\n")
                f.write("\n")
            
            # Recommendations
            f.write("## Recommendations\n")
            if self.checks_failed > 0:
                f.write("🚫 **DO NOT PROCEED WITH DEPLOYMENT**\n")
                f.write("Please address all issues before deploying to mainnet.\n")
            else:
                f.write("✅ **READY FOR DEPLOYMENT**\n")
                f.write("All checks passed. System is ready for mainnet deployment.\n")
            
            # Next Steps
            f.write("\n## Next Steps\n")
            if self.checks_failed > 0:
                f.write("1. Address all issues listed above\n")
                f.write("2. Run readiness check again\n")
                f.write("3. Review deployment documentation\n")
            else:
                f.write("1. Review deployment documentation\n")
                f.write("2. Execute deployment script\n")
                f.write("3. Monitor system performance\n")
            
        return str(report_path)

async def main():
    """Main execution function."""
    try:
        checker = MainnetReadinessChecker('config/test.config.json')
        
        # Run all checks
        checks = [
            checker.check_node_connection(),
            checker.check_contract_deployments(),
            checker.check_wallet_balance(),
            checker.check_gas_prices(),
            checker.check_test_coverage(),
            checker.check_monitoring_setup()
        ]
        
        await asyncio.gather(*checks)
        
        # Generate report
        report_path = checker.generate_report()
        logger.info(f"Report generated: {report_path}")
        
        # Exit with appropriate status
        sys.exit(0 if checker.checks_failed == 0 else 1)
        
    except Exception as e:
        logger.error(f"Error running readiness check: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
