from typing import Dict, List, Tuple, Optional
import asyncio
import time
from decimal import Decimal
from web3 import Web3
from cachetools import TTLCache
import aiohttp
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class ArbitrageOpportunity:
    buy_dex: str
    sell_dex: str
    token_address: str
    base_token_address: str
    buy_price: Decimal
    sell_price: Decimal
    potential_profit: Decimal
    gas_cost: Decimal
    net_profit: Decimal
    timestamp: float

class DexProtocol(ABC):
    @abstractmethod
    async def get_price(self, token_address: str, base_token_address: str) -> Decimal:
        pass

class UniswapV2Protocol(DexProtocol):
    def __init__(self, w3, router_address, factory_address):
        self.w3 = w3
        self.router_address = router_address
        self.factory_address = factory_address

    async def get_price(self, token_address: str, base_token_address: str) -> Decimal:
        # Implementation for getting price from Uniswap V2
        pair_address = self._get_pair_address(token_address, base_token_address)
        reserves = await self._get_reserves(pair_address)
        return self._calculate_price(reserves, token_address, base_token_address)

class UniswapV3Protocol(DexProtocol):
    def __init__(self, w3, pool_address):
        self.w3 = w3
        self.pool_address = pool_address

    async def get_price(self, token_address: str, base_token_address: str) -> Decimal:
        # Implementation for getting price from Uniswap V3
        slot0 = await self._get_slot0()
        return self._calculate_price_from_sqrt_price_x96(slot0['sqrtPriceX96'])

class SushiswapProtocol(DexProtocol):
    def __init__(self, w3, router_address, factory_address):
        self.w3 = w3
        self.router_address = router_address
        self.factory_address = factory_address

    async def get_price(self, token_address: str, base_token_address: str) -> Decimal:
        # Similar to Uniswap V2 implementation with Sushiswap specific adjustments
        pass

class PriceMonitor:
    def __init__(self, w3: Web3, config: dict, notification_manager=None):
        self.w3 = w3
        self.config = config
        self.notification_manager = notification_manager
        
        # Initialize price cache with 30-second TTL
        self.price_cache = TTLCache(maxsize=100, ttl=30)
        
        # Rate limiting settings
        self.request_times = []
        self.max_requests_per_second = 10
        
        # Initialize DEX protocols
        self.protocols = {
            'uniswap_v2': UniswapV2Protocol(
                w3,
                config['uniswap_v2_router'],
                config['uniswap_v2_factory']
            ),
            'uniswap_v3': UniswapV3Protocol(
                w3,
                config['uniswap_v3_pool']
            ),
            'sushiswap': SushiswapProtocol(
                w3,
                config['sushiswap_router'],
                config['sushiswap_factory']
            )
        }
        
        # Track monitored pairs
        self.monitored_pairs = config['monitored_pairs']
        
        # Initialize asyncio lock for thread-safe operations
        self.lock = asyncio.Lock()
    
    async def _enforce_rate_limit(self):
        """Enforce rate limiting for API calls"""
        async with self.lock:
            current_time = time.time()
            self.request_times = [t for t in self.request_times if current_time - t < 1.0]
            
            if len(self.request_times) >= self.max_requests_per_second:
                sleep_time = 1.0 - (current_time - self.request_times[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            self.request_times.append(current_time)
    
    def _get_cache_key(self, protocol: str, token_address: str, base_token_address: str) -> str:
        """Generate cache key for price data"""
        return f"{protocol}:{token_address}:{base_token_address}"
    
    async def get_price(self, protocol: str, token_address: str, base_token_address: str) -> Decimal:
        """Get price for a token pair from specified protocol with caching"""
        cache_key = self._get_cache_key(protocol, token_address, base_token_address)
        
        # Check cache first
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]
        
        # Enforce rate limiting
        await self._enforce_rate_limit()
        
        # Fetch price from protocol
        price = await self.protocols[protocol].get_price(token_address, base_token_address)
        
        # Update cache
        self.price_cache[cache_key] = price
        
        return price
    
    async def calculate_arbitrage_opportunity(
        self,
        token_address: str,
        base_token_address: str
    ) -> Optional[ArbitrageOpportunity]:
        """Calculate potential arbitrage opportunity between DEXes"""
        prices = {}
        
        # Fetch prices from all protocols
        for protocol_name in self.protocols:
            try:
                prices[protocol_name] = await self.get_price(
                    protocol_name,
                    token_address,
                    base_token_address
                )
            except Exception as e:
                if self.notification_manager:
                    await self.notification_manager.send_error(
                        f"Error fetching price from {protocol_name}: {str(e)}"
                    )
                continue
        
        # Find best buy and sell prices
        buy_dex = min(prices.items(), key=lambda x: x[1])
        sell_dex = max(prices.items(), key=lambda x: x[1])
        
        # Calculate potential profit
        buy_price = buy_dex[1]
        sell_price = sell_dex[1]
        
        if sell_price <= buy_price:
            return None
        
        # Estimate gas costs
        gas_cost = self._estimate_gas_cost()
        
        # Calculate net profit
        potential_profit = sell_price - buy_price
        net_profit = potential_profit - gas_cost
        
        if net_profit > self.config['min_profit_threshold']:
            return ArbitrageOpportunity(
                buy_dex=buy_dex[0],
                sell_dex=sell_dex[0],
                token_address=token_address,
                base_token_address=base_token_address,
                buy_price=buy_price,
                sell_price=sell_price,
                potential_profit=potential_profit,
                gas_cost=gas_cost,
                net_profit=net_profit,
                timestamp=time.time()
            )
        
        return None
    
    def _estimate_gas_cost(self) -> Decimal:
        """Estimate gas cost for arbitrage transaction"""
        gas_price = self.w3.eth.gas_price
        estimated_gas = self.config['estimated_gas_limit']
        return Decimal(gas_price * estimated_gas) / Decimal(10**18)
    
    async def monitor_prices(self):
        """Main loop for monitoring prices and detecting arbitrage opportunities"""
        while True:
            for pair in self.monitored_pairs:
                try:
                    opportunity = await self.calculate_arbitrage_opportunity(
                        pair['token_address'],
                        pair['base_token_address']
                    )
                    
                    if opportunity and self.notification_manager:
                        await self.notification_manager.send_opportunity_alert(opportunity)
                        
                except Exception as e:
                    if self.notification_manager:
                        await self.notification_manager.send_error(
                            f"Error monitoring pair {pair}: {str(e)}"
                        )
            
            await asyncio.sleep(self.config['price_update_interval'])
    
    async def start_monitoring(self):
        """Start the price monitoring process"""
        await self.monitor_prices()
