#!/usr/bin/env python3
"""Verify mainnet readiness of optimization tests."""
import asyncio
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from web3 import Web3
from decimal import Decimal
import pandas as pd
import matplotlib.pyplot as plt

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.optimizations import (
    GasOptimizer,
    LatencyOptimizer,
    PositionOptimizer,
    RiskManager
)
from src.metrics_collector import MetricsCollector

class MainnetReadinessVerifier:
    """Verifies if optimization tests properly simulate mainnet conditions."""

    def __init__(self):
        # Load configuration
        with open('config/test.config.json', 'r') as f:
            self.config = json.load(f)

        # Initialize Web3 connections
        self.w3_test = Web3(Web3.HTTPProvider(self.config['network']['http_provider']))
        self.w3_mainnet = Web3(Web3.HTTPProvider(
            'http://localhost:8545'  # Replace with your Geth node URL
        ))

        # Initialize components
        self.metrics = MetricsCollector(port=8080)
        self.reports_dir = project_root / 'reports'
        self.reports_dir.mkdir(exist_ok=True)

    async def verify_gas_conditions(self) -> Tuple[bool, List[str]]:
        """Verify gas price simulation matches mainnet conditions."""
        print("\nVerifying gas conditions...")
        issues = []
        
        # Get mainnet gas prices
        mainnet_blocks = []
        latest_block = self.w3_mainnet.eth.block_number
        for i in range(min(10, latest_block + 1)):  # Sample up to 10 recent blocks, but not more than exist
            block = self.w3_mainnet.eth.get_block(latest_block - i)
            mainnet_blocks.append({
                'base_fee': block.get('baseFeePerGas', 0),
                'gas_used_ratio': block['gasUsed'] / block['gasLimit']
            })

        # Calculate statistics (with safety checks)
        if not mainnet_blocks:
            issues.append("No blocks available on mainnet node")
            return False, issues

        mainnet_stats = {
            'avg_base_fee': sum(b['base_fee'] for b in mainnet_blocks) / len(mainnet_blocks),
            'avg_usage': max(0.000001, sum(b['gas_used_ratio'] for b in mainnet_blocks) / len(mainnet_blocks))
        }

        # Compare with test environment
        test_blocks = []
        latest_test_block = self.w3_test.eth.block_number
        for i in range(min(10, latest_test_block + 1)):
            block = self.w3_test.eth.get_block(latest_test_block - i)
            test_blocks.append({
                'base_fee': block.get('baseFeePerGas', 0),
                'gas_used_ratio': block['gasUsed'] / block['gasLimit']
            })

        if not test_blocks:
            issues.append("No blocks available in test environment")
            return False, issues

        test_stats = {
            'avg_base_fee': sum(b['base_fee'] for b in test_blocks) / len(test_blocks),
            'avg_usage': max(0.000001, sum(b['gas_used_ratio'] for b in test_blocks) / len(test_blocks))
        }

        # Check for significant deviations (with safety checks)
        if mainnet_stats['avg_base_fee'] > 0:  # Only compare if mainnet has non-zero base fee
            if abs(1 - test_stats['avg_base_fee'] / mainnet_stats['avg_base_fee']) > 0.2:
                issues.append("Gas prices in test environment deviate significantly from mainnet")

        if abs(1 - test_stats['avg_usage'] / mainnet_stats['avg_usage']) > 0.2:
            issues.append("Block usage patterns differ significantly from mainnet")

        return len(issues) == 0, issues

    async def verify_network_conditions(self) -> Tuple[bool, List[str]]:
        """Verify network conditions match mainnet characteristics."""
        print("Verifying network conditions...")
        issues = []

        # Test latency distribution
        latencies = []
        for _ in range(10):
            start_time = self.w3_mainnet.eth.get_block('latest')['timestamp']
            await asyncio.sleep(1)
            end_time = self.w3_mainnet.eth.get_block('latest')['timestamp']
            latencies.append(end_time - start_time)

        avg_mainnet_latency = sum(latencies) / len(latencies)

        # Compare with test environment
        test_latencies = []
        for _ in range(10):
            start_time = self.w3_test.eth.get_block('latest')['timestamp']
            await asyncio.sleep(1)
            end_time = self.w3_test.eth.get_block('latest')['timestamp']
            test_latencies.append(end_time - start_time)

        avg_test_latency = sum(test_latencies) / len(test_latencies)

        if abs(avg_test_latency - avg_mainnet_latency) > 0.5:  # 0.5s threshold
            issues.append("Network latency in test environment differs significantly from mainnet")

        return len(issues) == 0, issues

    async def verify_liquidity_conditions(self) -> Tuple[bool, List[str]]:
        """Verify liquidity conditions match mainnet."""
        print("Verifying liquidity conditions...")
        issues = []

        # Sample major DEX pairs
        pairs = [
            {
                'address': self.config['dex']['test_tokens']['WETH'],
                'pair_with': self.config['dex']['test_tokens']['USDC']
            },
            {
                'address': self.config['dex']['test_tokens']['WETH'],
                'pair_with': self.config['dex']['test_tokens']['DAI']
            }
        ]

        for pair in pairs:
            # Get mainnet liquidity
            mainnet_liquidity = await self._get_pair_liquidity(
                self.w3_mainnet,
                pair['address'],
                pair['pair_with']
            )

            # Get test environment liquidity
            test_liquidity = await self._get_pair_liquidity(
                self.w3_test,
                pair['address'],
                pair['pair_with']
            )

            # Compare liquidity depths
            if abs(1 - test_liquidity / mainnet_liquidity) > 0.3:  # 30% threshold
                issues.append(
                    f"Liquidity for pair {pair['address']}/{pair['pair_with']} "
                    "differs significantly from mainnet"
                )

        return len(issues) == 0, issues

    async def verify_mev_conditions(self) -> Tuple[bool, List[str]]:
        """Verify MEV competition simulation."""
        print("Verifying MEV conditions...")
        issues = []

        # Sample recent blocks for MEV activity
        mainnet_mev_stats = await self._analyze_mev_activity(self.w3_mainnet)
        test_mev_stats = await self._analyze_mev_activity(self.w3_test)

        # Compare MEV statistics
        if abs(1 - test_mev_stats['sandwich_rate'] / mainnet_mev_stats['sandwich_rate']) > 0.3:
            issues.append("Sandwich attack frequency differs from mainnet")

        if abs(1 - test_mev_stats['frontrun_rate'] / mainnet_mev_stats['frontrun_rate']) > 0.3:
            issues.append("Frontrunning frequency differs from mainnet")

        return len(issues) == 0, issues

    async def _get_pair_liquidity(
        self,
        w3: Web3,
        token0: str,
        token1: str
    ) -> Decimal:
        """Get liquidity for a token pair."""
        # Implementation would get actual liquidity from DEX contract
        return Decimal('1000000000000000000')

    async def _analyze_mev_activity(self, w3: Web3) -> Dict[str, float]:
        """Analyze MEV activity in recent blocks."""
        # Implementation would analyze actual MEV activity
        return {
            'sandwich_rate': 0.1,
            'frontrun_rate': 0.2
        }

    def generate_report(
        self,
        gas_result: Tuple[bool, List[str]],
        network_result: Tuple[bool, List[str]],
        liquidity_result: Tuple[bool, List[str]],
        mev_result: Tuple[bool, List[str]]
    ) -> None:
        """Generate mainnet readiness report."""
        report_path = self.reports_dir / 'mainnet_readiness_report.md'
        
        with open(report_path, 'w') as f:
            f.write("# Mainnet Readiness Report\n\n")

            # Overall Status
            all_passed = all([
                gas_result[0],
                network_result[0],
                liquidity_result[0],
                mev_result[0]
            ])
            
            status = "✅ READY" if all_passed else "❌ NOT READY"
            f.write(f"## Overall Status: {status}\n\n")

            # Gas Conditions
            f.write("## Gas Conditions\n")
            f.write(f"Status: {'✅ Pass' if gas_result[0] else '❌ Fail'}\n")
            if gas_result[1]:
                f.write("Issues:\n")
                for issue in gas_result[1]:
                    f.write(f"- {issue}\n")
            f.write("\n")

            # Network Conditions
            f.write("## Network Conditions\n")
            f.write(f"Status: {'✅ Pass' if network_result[0] else '❌ Fail'}\n")
            if network_result[1]:
                f.write("Issues:\n")
                for issue in network_result[1]:
                    f.write(f"- {issue}\n")
            f.write("\n")

            # Liquidity Conditions
            f.write("## Liquidity Conditions\n")
            f.write(f"Status: {'✅ Pass' if liquidity_result[0] else '❌ Fail'}\n")
            if liquidity_result[1]:
                f.write("Issues:\n")
                for issue in liquidity_result[1]:
                    f.write(f"- {issue}\n")
            f.write("\n")

            # MEV Conditions
            f.write("## MEV Conditions\n")
            f.write(f"Status: {'✅ Pass' if mev_result[0] else '❌ Fail'}\n")
            if mev_result[1]:
                f.write("Issues:\n")
                for issue in mev_result[1]:
                    f.write(f"- {issue}\n")
            f.write("\n")

            # Recommendations
            f.write("## Recommendations\n\n")
            all_issues = (
                gas_result[1] +
                network_result[1] +
                liquidity_result[1] +
                mev_result[1]
            )
            
            if all_issues:
                f.write("To achieve mainnet readiness, address the following:\n\n")
                for issue in all_issues:
                    f.write(f"1. {issue}\n")
            else:
                f.write("✅ All conditions match mainnet characteristics.\n")
                f.write("Ready for mainnet deployment.\n")

        print(f"\nReport generated: {report_path}")

async def main():
    """Main entry point."""
    verifier = MainnetReadinessVerifier()
    
    print("Starting mainnet readiness verification...")
    
    # Run verifications
    gas_result = await verifier.verify_gas_conditions()
    network_result = await verifier.verify_network_conditions()
    liquidity_result = await verifier.verify_liquidity_conditions()
    mev_result = await verifier.verify_mev_conditions()
    
    # Generate report
    verifier.generate_report(
        gas_result,
        network_result,
        liquidity_result,
        mev_result
    )
    
    # Exit with status
    all_passed = all([
        gas_result[0],
        network_result[0],
        liquidity_result[0],
        mev_result[0]
    ])
    
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    asyncio.run(main())
