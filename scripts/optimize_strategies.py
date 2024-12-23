"""Strategy Optimization Script"""
import asyncio
import time
import statistics
from decimal import Decimal
from typing import Dict, List
import matplotlib.pyplot as plt
import numpy as np
from web3 import Web3

from src.strategies.sandwich_v3 import SandwichStrategyV3
from src.strategies.frontrun_v3 import FrontrunStrategyV3
from src.strategies.jit_v3 import JITLiquidityStrategyV3
from test.test_strategy_performance_v2 import (
    create_test_tx,
    strategies,
    NUM_ITERATIONS,
    LATENCY_THRESHOLD_MS
)

class StrategyOptimizer:
    """Optimizer for MEV strategies"""
    
    def __init__(self):
        """Initialize optimizer"""
        self.results_dir = "optimization/results"
        self.plots_dir = "optimization/plots"
        
        # Create directories if they don't exist
        for directory in [self.results_dir, self.plots_dir]:
            os.makedirs(directory, exist_ok=True)
    
    async def run_latency_analysis(self, strategies_dict):
        """Run detailed latency analysis"""
        results = {
            'sandwich': [],
            'frontrun': [],
            'jit': []
        }
        
        # Run analysis phase tests
        print("\nRunning latency analysis...")
        for i in range(NUM_ITERATIONS):
            if i % 10 == 0:
                print(f"Progress: {i}/{NUM_ITERATIONS}")
                
            tx = create_test_tx()
            
            for strategy_name, strategy in strategies_dict.items():
                start = time.perf_counter()
                await strategy.analyze_transaction(tx)
                end = time.perf_counter()
                results[strategy_name].append((end - start) * 1000)
        
        return results
    
    async def run_memory_analysis(self, strategies_dict):
        """Run memory usage analysis"""
        import psutil
        import os
        
        results = {
            'sandwich': [],
            'frontrun': [],
            'jit': []
        }
        
        process = psutil.Process(os.getpid())
        
        print("\nRunning memory analysis...")
        for i in range(NUM_ITERATIONS):
            if i % 10 == 0:
                print(f"Progress: {i}/{NUM_ITERATIONS}")
                
            tx = create_test_tx()
            
            for strategy_name, strategy in strategies_dict.items():
                # Get memory before
                mem_before = process.memory_info().rss
                
                # Run analysis
                await strategy.analyze_transaction(tx)
                
                # Get memory after
                mem_after = process.memory_info().rss
                
                # Record memory increase in MB
                mem_increase = (mem_after - mem_before) / (1024 * 1024)
                results[strategy_name].append(mem_increase)
        
        return results
    
    def plot_latency_distribution(self, results: Dict[str, List[float]], save_path: str):
        """Plot latency distribution for each strategy"""
        plt.figure(figsize=(12, 6))
        
        for strategy_name, latencies in results.items():
            plt.hist(latencies, bins=30, alpha=0.5, label=strategy_name)
        
        plt.axvline(x=LATENCY_THRESHOLD_MS, color='r', linestyle='--', label='Threshold')
        plt.xlabel('Latency (ms)')
        plt.ylabel('Frequency')
        plt.title('Strategy Latency Distribution')
        plt.legend()
        plt.grid(True)
        plt.savefig(save_path)
        plt.close()
    
    def plot_memory_usage(self, results: Dict[str, List[float]], save_path: str):
        """Plot memory usage for each strategy"""
        plt.figure(figsize=(12, 6))
        
        for strategy_name, memory_usage in results.items():
            plt.plot(memory_usage, label=strategy_name)
        
        plt.xlabel('Iteration')
        plt.ylabel('Memory Usage (MB)')
        plt.title('Strategy Memory Usage Over Time')
        plt.legend()
        plt.grid(True)
        plt.savefig(save_path)
        plt.close()
    
    def generate_optimization_report(self, latency_results: Dict, memory_results: Dict):
        """Generate optimization report"""
        report = []
        report.append("MEV Strategy Optimization Report")
        report.append("============================\n")
        
        # Latency Analysis
        report.append("Latency Analysis")
        report.append("-----------------")
        for strategy, latencies in latency_results.items():
            avg = statistics.mean(latencies)
            p95 = statistics.quantiles(latencies, n=20)[18]
            p99 = statistics.quantiles(latencies, n=100)[98]
            
            report.append(f"\n{strategy.upper()} Strategy:")
            report.append(f"Average Latency: {avg:.2f}ms")
            report.append(f"95th Percentile: {p95:.2f}ms")
            report.append(f"99th Percentile: {p99:.2f}ms")
            
            # Optimization recommendations
            report.append("\nOptimization Recommendations:")
            if avg > LATENCY_THRESHOLD_MS * 0.8:
                report.append("- Consider implementing parallel processing for transaction analysis")
                report.append("- Cache frequently accessed data")
                report.append("- Optimize price impact calculations")
            
            if p99 > LATENCY_THRESHOLD_MS * 1.5:
                report.append("- Implement circuit breakers for high latency scenarios")
                report.append("- Add fallback mechanisms for peak load")
        
        # Memory Analysis
        report.append("\n\nMemory Analysis")
        report.append("---------------")
        for strategy, memory_usage in memory_results.items():
            avg_mem = statistics.mean(memory_usage)
            max_mem = max(memory_usage)
            
            report.append(f"\n{strategy.upper()} Strategy:")
            report.append(f"Average Memory Usage: {avg_mem:.2f}MB")
            report.append(f"Peak Memory Usage: {max_mem:.2f}MB")
            
            # Memory optimization recommendations
            report.append("\nMemory Optimization Recommendations:")
            if max_mem > 100:  # If peak memory usage exceeds 100MB
                report.append("- Implement memory pooling for frequent allocations")
                report.append("- Add garbage collection triggers")
                report.append("- Consider using memory-mapped files for large datasets")
        
        # General Recommendations
        report.append("\n\nGeneral Optimization Recommendations")
        report.append("----------------------------------")
        report.append("1. Infrastructure:")
        report.append("   - Deploy dedicated nodes for each strategy")
        report.append("   - Implement redundancy for critical components")
        report.append("   - Use load balancing for high-traffic periods")
        
        report.append("\n2. Network Optimization:")
        report.append("   - Optimize RPC endpoint connections")
        report.append("   - Implement websocket connections for real-time updates")
        report.append("   - Consider using private mempool services")
        
        report.append("\n3. Code Optimization:")
        report.append("   - Profile hot code paths")
        report.append("   - Implement caching for frequently accessed data")
        report.append("   - Use compiled languages for critical sections")
        
        # Write report to file
        report_path = f"{self.results_dir}/optimization_report.txt"
        with open(report_path, 'w') as f:
            f.write('\n'.join(report))
        
        return report_path

async def main():
    """Main optimization function"""
    optimizer = StrategyOptimizer()
    
    # Get strategies
    strategies_dict = await strategies()
    
    # Run analysis
    latency_results = await optimizer.run_latency_analysis(strategies_dict)
    memory_results = await optimizer.run_memory_analysis(strategies_dict)
    
    # Generate plots
    optimizer.plot_latency_distribution(
        latency_results,
        f"{optimizer.plots_dir}/latency_distribution.png"
    )
    optimizer.plot_memory_usage(
        memory_results,
        f"{optimizer.plots_dir}/memory_usage.png"
    )
    
    # Generate report
    report_path = optimizer.generate_optimization_report(latency_results, memory_results)
    
    print(f"\nOptimization analysis complete!")
    print(f"Report saved to: {report_path}")
    print(f"Plots saved to: {optimizer.plots_dir}/")

if __name__ == "__main__":
    import os
    asyncio.run(main())
