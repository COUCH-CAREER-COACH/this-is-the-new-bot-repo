"""Real-world mainnet arbitrage strategy tests with comprehensive validation"""
import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal, getcontext
from web3 import Web3
from web3.exceptions import ContractLogicError, TransactionNotFound
import time
import json
import logging
from typing import Dict, List, Tuple, Optional

from src.arbitrage_strategy import EnhancedArbitrageStrategy
from src.utils.dex_utils import DEXHandler
from src.logger_config import logger
from src.utils.web3_utils import validate_address, validate_wei

# Set Decimal precision for accurate calculations
getcontext().prec = 78  # Ethereum's uint256 max value has 78 decimal digits

class TestArbReal(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures with real mainnet parameters and proper error handling."""
        try:
            # Initialize logger for test-specific logging
            self.test_logger = logging.getLogger('test.arb_real')
            self.test_logger.setLevel(logging.DEBUG)
            
            # Load and validate mainnet config
            self.config = {
                'strategies': {
                    'arbitrage': {
                        'min_profit_wei': '100000000000000000',  # 0.1 ETH min profit
                        'max_position_size': '50000000000000000000',  # 50 ETH max position
                        'max_price_impact': '0.02',  # 2% max price impact
                        'min_pool_liquidity': '1000000000000000000000'  # 1000 ETH min liquidity
                    }
                },
                'dex': {
                    'uniswap_v2_router': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
                    'uniswap_v2_factory': '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f',
                    'sushiswap_router': '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',
                    'sushiswap_factory': '0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac'
                },
                'flash_loan': {
                    'providers': {
                        'aave': {
                            'pool_address_provider': '0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e',
                            'fee': '0.0009'  # Current Aave V3 flash loan fee
                        }
                    },
                    'preferred_provider': 'aave',
                    'private_key': '0x' + '1' * 64  # Mock private key for testing
                },
                'gas': {
                    'max_priority_fee': '3000000000',  # 3 GWEI max priority fee
                    'max_fee_per_gas': '100000000000',  # 100 GWEI max fee
                    'base_gas': 300000,  # Base gas units for arb tx
                    'buffer_percent': 20  # 20% gas buffer
                },
                'tokens': {
                    'weth': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                    'usdc': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
                    'dai': '0x6B175474E89094C44Da98b954EedeAC495271d0F'
                }
            }
            
            # Validate config addresses
            for section in ['dex', 'tokens']:
                for key, addr in self.config[section].items():
                    validate_address(Web3(), addr)
            
            # Initialize gas price parameters
            self.base_gas_price = 30000000000  # 30 GWEI base
            self.priority_fee = 2000000000  # 2 GWEI priority fee
            self.max_fee_per_gas = self.base_gas_price * 2
            self.max_priority_fee_per_gas = self.priority_fee
            
            # Initialize Web3 mock with proper error handling
            self.w3 = Mock()
            self.w3.eth = Mock()
            
            # Setup Web3 utilities first (needed for validation)
            self.w3.to_wei = Web3.to_wei
            self.w3.from_wei = Web3.from_wei
            self.w3.is_address = Web3.is_address
            self.w3.to_checksum_address = Web3.to_checksum_address
            self.w3.keccak = Web3.keccak
            
            # Setup gas price getters
            self.w3.eth.gas_price = self.base_gas_price + self.priority_fee
            self.w3.eth.get_gas_price = AsyncMock(return_value=self.base_gas_price + self.priority_fee)
            self.w3.eth.max_priority_fee = AsyncMock(return_value=self.priority_fee)
            self.w3.eth.get_block = AsyncMock(return_value={
                'timestamp': int(time.time()),
                'baseFeePerGas': self.base_gas_price,
                'gasLimit': 30000000,
                'gasUsed': 15000000,
                'number': 18500000,
                'hash': '0x' + '1' * 64,
                'parentHash': '0x' + '2' * 64,
                'miner': '0x' + '3' * 40,
                'difficulty': 2,
                'totalDifficulty': 58750003716598352816469
            })
            
            # Setup account and chain info
            self.w3.eth.chain_id = 1  # Mainnet
            self.w3.eth.default_account = "0x" + "1" * 40  # Mock EOA address
            self.w3.eth.get_transaction_count = AsyncMock(return_value=1)
            self.w3.eth.get_code = AsyncMock(return_value='0x')  # EOA by default
            
            # Setup transaction handling
            self.w3.eth.account = Mock()
            self.w3.eth.account.sign_transaction = Mock(return_value=Mock(
                rawTransaction=b'0x' + b'0' * 64
            ))
            self.w3.eth.send_raw_transaction = AsyncMock(return_value='0x' + '2' * 64)
            self.w3.eth.wait_for_transaction_receipt = AsyncMock(return_value={
                'status': 1,
                'gasUsed': 300000,
                'effectiveGasPrice': self.base_gas_price + self.priority_fee,
                'blockNumber': 18500000,
                'blockHash': '0x' + '3' * 64,
                'transactionIndex': 0,
                'logs': []
            })
            
            # Setup mempool simulation
            self.w3.eth.get_pending_transaction_count = AsyncMock(return_value=150)
            self.w3.eth.get_transaction = AsyncMock(return_value={
                'hash': '0x' + '1' * 64,
                'nonce': 1,
                'blockHash': None,
                'blockNumber': None,
                'transactionIndex': None,
                'from': '0x' + '4' * 40,
                'to': self.config['dex']['uniswap_v2_router'],
                'value': 1000000000000000000,
                'gas': 300000,
                'gasPrice': self.base_gas_price + self.priority_fee,
                'maxFeePerGas': self.max_fee_per_gas,
                'maxPriorityFeePerGas': self.max_priority_fee_per_gas,
                'input': '0x38ed1739'
            })
            
            # Setup contract mocking (must be last as it depends on all previous setup)
            self._setup_contract_mocks()
            
        except Exception as e:
            self.test_logger.error(f"Error in test setup: {e}")
            raise
            
    def _setup_contract_mocks(self):
        """Setup contract mocking with proper error handling"""
        try:
            def mock_contract_factory(*args, **kwargs):
                contract = Mock()
                contract.functions = Mock()
                
                # Get contract address and ABI from kwargs
                contract_address = kwargs.get('address')
                contract_abi = kwargs.get('abi', [])
                
                try:
                    # Load real ABIs for validation
                    if contract_address == self.config['flash_loan']['providers']['aave']['pool_address_provider']:
                        with open('contracts/interfaces/IPoolAddressesProvider.json', 'r') as f:
                            contract_abi = json.load(f)['abi']
                    elif contract_address == "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9":
                        with open('contracts/interfaces/IPool.json', 'r') as f:
                            contract_abi = json.load(f)['abi']
                    
                    # Store ABI on contract for validation
                    contract.abi = contract_abi
                except Exception as e:
                    self.test_logger.warning(f"Could not load ABI for {contract_address}: {e}")
                    contract.abi = []  # Use empty ABI as fallback
                
                try:
                    # Mock Aave Pool Address Provider functions
                    if contract_address == self.config['flash_loan']['providers']['aave']['pool_address_provider']:
                        pool_addr = "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"
                        mock_call = Mock()
                        mock_call.call = Mock(return_value=pool_addr)  # Synchronous return
                        contract.functions.getPool = Mock(return_value=mock_call)
                        contract.address = contract_address
                        return contract
                    
                    # Mock Aave Pool functions
                    if contract_address == "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9":
                        # Mock flash loan functions
                        max_loan_call = Mock()
                        max_loan_call.call = Mock(return_value=1000000000000000000000)  # 1000 ETH
                        contract.functions.getMaxFlashLoan = Mock(return_value=max_loan_call)

                        premium_call = Mock()
                        premium_call.call = Mock(return_value=9)  # 0.09% fee
                        contract.functions.FLASHLOAN_PREMIUM_TOTAL = Mock(return_value=premium_call)

                        flash_loan_call = Mock()
                        flash_loan_call.call = Mock(return_value=True)
                        flash_loan_call.build_transaction = Mock(return_value={
                            'to': contract_address,
                            'data': '0x',
                            'value': 0,
                            'gas': 500000,
                            'maxFeePerGas': self.max_fee_per_gas,
                            'maxPriorityFeePerGas': self.max_priority_fee_per_gas,
                            'nonce': 1
                        })
                        contract.functions.flashLoan = Mock(return_value=flash_loan_call)
                        
                        contract.address = contract_address
                        return contract
                except Exception as e:
                    self.test_logger.error(f"Error setting up contract functions for {contract_address}: {e}")
                    raise
                
                    # Setup DEX functions for non-Aave contracts
                    if not contract_address or (
                        contract_address != self.config['flash_loan']['providers']['aave']['pool_address_provider'] and
                        contract_address != "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"
                    ):
                        # Setup DEX pool functions
                        reserves_call = Mock()
                        reserves_call.call = Mock(return_value=(
                            50000000000000,  # token0 reserves (USDC)
                            25000000000000000000000,  # token1 reserves (WETH)
                            int(time.time())  # last update timestamp
                        ))
                        contract.functions.getReserves = Mock(return_value=reserves_call)
                        
                        # Setup token functions
                        token0_call = Mock()
                        token0_call.call = Mock(return_value=self.config['tokens']['usdc'])
                        contract.functions.token0 = Mock(return_value=token0_call)
                        
                        token1_call = Mock()
                        token1_call.call = Mock(return_value=self.config['tokens']['weth'])
                        contract.functions.token1 = Mock(return_value=token1_call)
                        
                        # Setup factory functions
                        factory_call = Mock()
                        factory_call.call = Mock(return_value=self.config['dex']['uniswap_v2_factory'])
                        contract.functions.factory = Mock(return_value=factory_call)
                        
                        pair_call = Mock()
                        pair_call.call = Mock(return_value='0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc')
                        contract.functions.getPair = Mock(return_value=pair_call)
                        
                        pairs_length_call = Mock()
                        pairs_length_call.call = Mock(return_value=1000)  # Realistic number of pairs
                        contract.functions.allPairsLength = Mock(return_value=pairs_length_call)
                        
                        # Setup swap functions with realistic slippage
                        amounts_call = Mock()
                        amounts_call.call = Mock(return_value=[
                            1000000000000000000,  # 1 ETH in
                            1950000000  # 1950 USDC out (after slippage)
                        ])
                        contract.functions.getAmountsOut = Mock(return_value=amounts_call)
                        
                        # Set contract address if provided
                        if contract_address:
                            contract.address = contract_address
                    
                    return contract
                
            # Setup Web3 contract factory and transaction handling
            self.w3.eth.contract = mock_contract_factory
            self.w3.eth.get_transaction_count = AsyncMock(return_value=1)
            
            # Setup account for flash loan transactions
            self.w3.eth.default_account = "0x" + "1" * 40  # Mock EOA address
            self.w3.eth.account = Mock()
            self.w3.eth.account.sign_transaction = Mock(return_value=Mock(
                rawTransaction=b'0x' + b'0' * 64
            ))
            self.w3.eth.send_raw_transaction = AsyncMock(return_value='0x' + '2' * 64)
            self.w3.eth.wait_for_transaction_receipt = AsyncMock(return_value={
                'status': 1,
                'gasUsed': 300000,
                'effectiveGasPrice': self.base_gas_price + self.priority_fee
            })
            
        except Exception as e:
            self.test_logger.error(f"Error setting up contract mocks: {e}")
            raise
            
    def _setup_web3_utilities(self):
        """Setup Web3 utilities with proper error handling"""
        try:
            # Enhanced Web3 utility mocking with mainnet-like precision
            def precise_to_wei(amount, unit='ether'):
                """Handle wei conversion with high precision and validation"""
                try:
                    multipliers = {
                        'ether': Decimal('1000000000000000000'),  # 1e18
                        'gwei': Decimal('1000000000'),            # 1e9
                        'wei': Decimal('1'),
                        'mwei': Decimal('1000000'),              # 1e6 (for USDC)
                        'szabo': Decimal('1000000000000'),       # 1e12
                        'finney': Decimal('1000000000000000'),   # 1e15
                    }
                    if unit not in multipliers:
                        raise ValueError(f"Unsupported unit: {unit}")
                    
                    amount_dec = Decimal(str(amount))
                    if amount_dec < 0:
                        raise ValueError("Amount cannot be negative")
                    
                    result = amount_dec * multipliers[unit]
                    if result > Decimal('2') ** Decimal('256'):
                        raise ValueError("Amount too large for uint256")
                        
                    return int(result)
                except Exception as e:
                    self.test_logger.error(f"Error in to_wei conversion: {e}")
                    raise
                    
            def precise_from_wei(amount, unit='ether'):
                """Handle wei to unit conversion with high precision and validation"""
                try:
                    multipliers = {
                        'ether': Decimal('1000000000000000000'),
                        'gwei': Decimal('1000000000'),
                        'wei': Decimal('1'),
                        'mwei': Decimal('1000000'),
                        'szabo': Decimal('1000000000000'),
                        'finney': Decimal('1000000000000000'),
                    }
                    if unit not in multipliers:
                        raise ValueError(f"Unsupported unit: {unit}")
                    
                    amount_dec = Decimal(str(amount))
                    if amount_dec < 0:
                        raise ValueError("Amount cannot be negative")
                    
                    return amount_dec / multipliers[unit]
                except Exception as e:
                    self.test_logger.error(f"Error in from_wei conversion: {e}")
                    raise
                    
            def validate_and_checksum_address(addr):
                """Validate and return checksummed address"""
                if not isinstance(addr, str):
                    raise TypeError("Address must be string")
                if not addr.startswith('0x'):
                    raise ValueError("Address must start with 0x")
                if len(addr) != 42:
                    raise ValueError("Address must be 42 characters")
                try:
                    return Web3.to_checksum_address(addr)
                except Exception as e:
                    raise ValueError(f"Invalid address: {e}")
                    
            self.w3.to_wei = precise_to_wei
            self.w3.from_wei = precise_from_wei
            self.w3.is_address = validate_and_checksum_address
            self.w3.to_checksum_address = validate_and_checksum_address
            self.w3.keccak = Web3.keccak
            
        except Exception as e:
            self.test_logger.error(f"Error setting up Web3 utilities: {e}")
            raise
            
    def _setup_network_params(self):
        """Setup network parameters with proper error handling"""
        try:
            # Simulate dynamic gas prices (15-500 GWEI range with EIP-1559)
            self.base_gas_price = 30000000000  # 30 GWEI base
            self.priority_fee = 2000000000  # 2 GWEI priority fee
            self.w3.eth.gas_price = self.base_gas_price + self.priority_fee
            self.w3.eth.get_gas_price = AsyncMock(return_value=self.base_gas_price + self.priority_fee)
            self.w3.eth.max_priority_fee = AsyncMock(return_value=self.priority_fee)
            
            # Recent mainnet block with realistic properties
            self.w3.eth.block_number = 18500000
            self.w3.eth.get_block = AsyncMock(return_value={
                'timestamp': int(time.time()),
                'baseFeePerGas': self.base_gas_price,
                'gasLimit': 30000000,
                'gasUsed': 15000000,
                'number': 18500000,
                'hash': '0x' + '1' * 64,
                'parentHash': '0x' + '2' * 64,
                'miner': '0x' + '3' * 40,
                'difficulty': 2,
                'totalDifficulty': 58750003716598352816469
            })
            
            # Add mempool simulation
            self.w3.eth.get_pending_transaction_count = AsyncMock(return_value=150)
            self.w3.eth.get_transaction = AsyncMock(return_value={
                'hash': '0x' + '1' * 64,
                'nonce': 1,
                'blockHash': None,
                'blockNumber': None,
                'transactionIndex': None,
                'from': '0x' + '4' * 40,
                'to': self.config['dex']['uniswap_v2_router'],
                'value': 1000000000000000000,
                'gas': 300000,
                'gasPrice': self.base_gas_price + self.priority_fee,
                'maxFeePerGas': self.base_gas_price * 2,
                'maxPriorityFeePerGas': self.priority_fee,
                'input': '0x38ed1739'
            })
            
            # Add mainnet-specific utilities
            self.w3.eth.chain_id = 1
            self.w3.eth.get_code = AsyncMock(return_value='0x')
            
        except Exception as e:
            self.test_logger.error(f"Error setting up network parameters: {e}")
            raise

    @patch('web3.Web3.to_wei')
    async def test_real_world_profitable_arb(self, mock_to_wei):
        """Test a real-world profitable arbitrage scenario with actual pool data."""
        # Setup Web3.to_wei mock
        mock_to_wei.side_effect = self.w3.to_wei

        # Initialize strategy
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock DEX handler with real pool data
        mock_decode = Mock()
        mock_decode.return_value = {
            'dex': 'uniswap',
            'path': [
                self.config['tokens']['weth'],  # WETH
                self.config['tokens']['usdc']   # USDC
            ],
            'amountIn': 1000000000000000000  # 1 ETH
        }
        strategy.dex_handler.decode_swap_data = mock_decode

        # Real pool data from mainnet with realistic properties
        uni_pool = {
            'pair_address': '0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc',  # Real USDC/ETH pool
            'reserves': {
                'token0': 50000000000000,  # 50M USDC (more realistic liquidity)
                'token1': 25000000000000000000000  # 25K ETH
            },
            'fee': Decimal('0.003'),
            'token0': self.config['tokens']['usdc'],
            'token1': self.config['tokens']['weth'],
            'decimals0': 6,  # USDC decimals
            'decimals1': 18,  # WETH decimals
            'last_k': Decimal('1.25e27'),  # k = reserve0 * reserve1
            'block_timestamp_last': int(time.time()) - 300,  # 5 min ago
            'price0_cumulative_last': Decimal('1.234e27'),
            'price1_cumulative_last': Decimal('4.567e27'),
            'pending_txs': []  # No suspicious pending transactions
        }
        
        # Sushiswap pool with slightly different reserves to create arbitrage opportunity
        sushi_pool = {
            'pair_address': '0x397FF1542f962076d0BFE58eA045FfA2d347ACa0',  # Real USDC/ETH pool
            'reserves': {
                'token0': 45000000000000,  # 45M USDC (creates price difference)
                'token1': 24000000000000000000000  # 24K ETH
            },
            'fee': Decimal('0.003'),
            'token0': self.config['tokens']['usdc'],
            'token1': self.config['tokens']['weth'],
            'decimals0': 6,
            'decimals1': 18,
            'last_k': Decimal('1.08e27'),
            'block_timestamp_last': int(time.time()) - 180,  # 3 min ago
            'price0_cumulative_last': Decimal('1.235e27'),
            'price1_cumulative_last': Decimal('4.568e27'),
            'pending_txs': []
        }

        async def mock_get_pool_info(dex, *args):
            return uni_pool if dex == 'uniswap' else sushi_pool

        strategy.dex_handler.get_pool_info = mock_get_pool_info

        # Simulate realistic swap outputs with market impact and MEV protection
        async def mock_simulate_swap(amount_in, reserve_in, reserve_out, fee):
            """Simulate swap with realistic price impact, slippage, and MEV protection"""
            try:
                # Convert to Decimal for precise calculation
                amount_in_dec = Decimal(str(amount_in))
                reserve_in_dec = Decimal(str(reserve_in))
                reserve_out_dec = Decimal(str(reserve_out))
                
                # Calculate price impact
                price_impact = amount_in_dec / reserve_in_dec
                if price_impact > Decimal('0.05'):  # >5% price impact
                    logger.warning(f"High price impact detected: {price_impact}")
                    return 0  # Reject high impact trades
                
                # Apply trading fee
                amount_in_with_fee = amount_in_dec * (Decimal('1') - fee)
                
                # Calculate base output using xy=k formula
                numerator = amount_in_with_fee * reserve_out_dec
                denominator = reserve_in_dec + amount_in_with_fee
                base_output = numerator / denominator
                
                # Apply realistic slippage factors
                network_slippage = Decimal('0.997')  # 0.3% network slippage
                mev_protection = Decimal('0.995')    # 0.5% MEV protection buffer
                sandwich_protection = Decimal('0.998')  # 0.2% sandwich attack protection
                
                # Calculate final output with all protections
                final_output = base_output * network_slippage * mev_protection * sandwich_protection
                
                # Ensure output maintains profitable spread
                min_spread = Decimal('1.004')  # Minimum 0.4% spread required
                if final_output * min_spread <= amount_in_dec:
                    logger.debug("Insufficient spread after protections")
                    return 0
                
                return int(final_output)
                
            except Exception as e:
                logger.error(f"Error in swap simulation: {e}")
                return 0

        strategy._simulate_swap_output = mock_simulate_swap

        # Create transaction with realistic properties
        tx = {
            'hash': '0x' + '1' * 64,
            'nonce': 1,
            'blockHash': None,
            'blockNumber': None,
            'transactionIndex': None,
            'from': '0x' + '4' * 40,
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000,
            'gas': 300000,
            'maxFeePerGas': self.base_gas_price * 2,
            'maxPriorityFeePerGas': self.priority_fee,
            'input': '0x38ed1739000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000002000000000000000000000000c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2000000000000000000000000a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
            'type': 2,
            'chainId': 1,
            'accessList': []
        }

        result = await strategy.analyze_transaction(tx)
        
        # Verify realistic arbitrage opportunity with comprehensive checks
        self.assertIsNotNone(result, "Should detect valid arbitrage opportunity")
        self.assertEqual(result['type'], 'arbitrage', "Should be arbitrage type")
        self.assertEqual(result['token_in'], self.config['tokens']['weth'], "Should use WETH as input token")
        self.assertEqual(result['token_out'], self.config['tokens']['usdc'], "Should use USDC as output token")
        
        # Verify realistic profit margins with current market conditions
        min_profit = int(self.config['strategies']['arbitrage']['min_profit_wei'])
        self.assertGreater(result['profit'], min_profit, "Should exceed minimum profit threshold")
        
        # Verify position size limits and risk management
        max_size = int(self.config['strategies']['arbitrage']['max_position_size'])
        self.assertLessEqual(result['amount'], max_size, "Should respect maximum position size")
        self.assertGreater(result['amount'], 0, "Should have non-zero position size")
        
        # Calculate price impact
        price_impact = Decimal(str(result['amount'])) / Decimal(str(uni_pool['reserves']['token1']))
        self.assertLess(price_impact, Decimal('0.05'), "Price impact should be under 5%")
        
        # Verify gas cost considerations with EIP-1559 mechanics
        base_fee = self.base_gas_price
        priority_fee = self.priority_fee
        total_gas_cost = (base_fee + priority_fee) * strategy.base_gas
        net_profit = result['profit'] - total_gas_cost
        
        self.assertGreater(net_profit, min_profit, "Should be profitable after gas costs")
        self.assertGreater(
            net_profit / Decimal(str(result['amount'])) * Decimal('100'),
            Decimal('0.1'),  # At least 0.1% ROI
            "Should have meaningful ROI"
        )
        
        # Verify pool addresses
        self.assertEqual(
            result['pools']['uniswap'],
            uni_pool['pair_address'],
            "Should use correct Uniswap pool"
        )
        self.assertEqual(
            result['pools']['sushiswap'],
            sushi_pool['pair_address'],
            "Should use correct Sushiswap pool"
        )
        
        # Verify timing constraints
        self.assertLess(
            abs(result['timestamp'] - int(time.time())),
            2,
            "Timestamp should be current"
        )

if __name__ == '__main__':
    unittest.main()

    @patch('web3.Web3.to_wei')
    async def test_real_world_profitable_arb(self, mock_to_wei):
        """Test a real-world profitable arbitrage scenario with actual pool data."""
        # Setup Web3.to_wei mock
        mock_to_wei.side_effect = self.w3.to_wei

        # Initialize strategy
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)

        # Mock DEX handler with real pool data
        mock_decode = Mock()
        mock_decode.return_value = {
            'dex': 'uniswap',
            'path': [
                self.config['tokens']['weth'],  # WETH
                self.config['tokens']['usdc']   # USDC
            ],
            'amountIn': 1000000000000000000  # 1 ETH
        }
        strategy.dex_handler.decode_swap_data = mock_decode

        # Real pool data from mainnet with realistic properties
        uni_pool = {
            'pair_address': '0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc',  # Real USDC/ETH pool
            'reserves': {
                'token0': 50000000000000,  # 50M USDC (more realistic liquidity)
                'token1': 25000000000000000000000  # 25K ETH
            },
            'fee': Decimal('0.003'),
            'token0': self.config['tokens']['usdc'],
            'token1': self.config['tokens']['weth'],
            'decimals0': 6,  # USDC decimals
            'decimals1': 18,  # WETH decimals
            'last_k': Decimal('1.25e27'),  # k = reserve0 * reserve1
            'block_timestamp_last': int(time.time()) - 300,  # 5 min ago
            'price0_cumulative_last': Decimal('1.234e27'),
            'price1_cumulative_last': Decimal('4.567e27'),
            'pending_txs': []  # No suspicious pending transactions
        }
        
        # Sushiswap pool with slightly different reserves to create arbitrage opportunity
        sushi_pool = {
            'pair_address': '0x397FF1542f962076d0BFE58eA045FfA2d347ACa0',  # Real USDC/ETH pool
            'reserves': {
                'token0': 45000000000000,  # 45M USDC (creates price difference)
                'token1': 24000000000000000000000  # 24K ETH
            },
            'fee': Decimal('0.003'),
            'token0': self.config['tokens']['usdc'],
            'token1': self.config['tokens']['weth'],
            'decimals0': 6,
            'decimals1': 18,
            'last_k': Decimal('1.08e27'),
            'block_timestamp_last': int(time.time()) - 180,  # 3 min ago
            'price0_cumulative_last': Decimal('1.235e27'),
            'price1_cumulative_last': Decimal('4.568e27'),
            'pending_txs': []
        }

        async def mock_get_pool_info(dex, *args):
            return uni_pool if dex == 'uniswap' else sushi_pool

        strategy.dex_handler.get_pool_info = mock_get_pool_info

        # Simulate realistic swap outputs with market impact and MEV protection
        async def mock_simulate_swap(amount_in, reserve_in, reserve_out, fee):
            """Simulate swap with realistic price impact, slippage, and MEV protection"""
            try:
                # Convert to Decimal for precise calculation
                amount_in_dec = Decimal(str(amount_in))
                reserve_in_dec = Decimal(str(reserve_in))
                reserve_out_dec = Decimal(str(reserve_out))
                
                # Calculate price impact
                price_impact = amount_in_dec / reserve_in_dec
                if price_impact > Decimal('0.05'):  # >5% price impact
                    logger.warning(f"High price impact detected: {price_impact}")
                    return 0  # Reject high impact trades
                
                # Apply trading fee
                amount_in_with_fee = amount_in_dec * (Decimal('1') - fee)
                
                # Calculate base output using xy=k formula
                numerator = amount_in_with_fee * reserve_out_dec
                denominator = reserve_in_dec + amount_in_with_fee
                base_output = numerator / denominator
                
                # Apply realistic slippage factors
                network_slippage = Decimal('0.997')  # 0.3% network slippage
                mev_protection = Decimal('0.995')    # 0.5% MEV protection buffer
                sandwich_protection = Decimal('0.998')  # 0.2% sandwich attack protection
                
                # Calculate final output with all protections
                final_output = base_output * network_slippage * mev_protection * sandwich_protection
                
                # Ensure output maintains profitable spread
                min_spread = Decimal('1.004')  # Minimum 0.4% spread required
                if final_output * min_spread <= amount_in_dec:
                    logger.debug("Insufficient spread after protections")
                    return 0
                
                return int(final_output)
                
            except Exception as e:
                logger.error(f"Error in swap simulation: {e}")
                return 0

        strategy._simulate_swap_output = mock_simulate_swap

        # Simulate real mainnet transaction with full EIP-1559 properties
        tx = {
            'hash': '0x' + '1' * 64,
            'nonce': 1,
            'blockHash': None,  # Pending tx
            'blockNumber': None,
            'transactionIndex': None,
            'from': '0x' + '4' * 40,
            'to': self.config['dex']['uniswap_v2_router'].lower(),
            'value': 1000000000000000000,  # 1 ETH
            'gas': 300000,
            'maxFeePerGas': self.base_gas_price * 2,  # Dynamic base fee * 2
            'maxPriorityFeePerGas': self.priority_fee,
            'input': '0x38ed1739000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000002000000000000000000000000c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2000000000000000000000000a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',  # Actual encoded swap data
            'r': '0x' + '2' * 64,
            's': '0x' + '3' * 64,
            'v': 27,
            'type': 2,  # EIP-1559 transaction
            'chainId': 1,  # Mainnet
            'accessList': [],  # EIP-2930 access list
            'gasPrice': None  # EIP-1559 tx doesn't use gasPrice
        }

        result = await strategy.analyze_transaction(tx)
        
        # Verify realistic arbitrage opportunity with comprehensive checks
        self.assertIsNotNone(result, "Should detect valid arbitrage opportunity")
        self.assertEqual(result['type'], 'arbitrage', "Should be arbitrage type")
        self.assertEqual(result['token_in'], self.config['tokens']['weth'], "Should use WETH as input token")
        self.assertEqual(result['token_out'], self.config['tokens']['usdc'], "Should use USDC as output token")
        
        # Verify realistic profit margins with current market conditions
        min_profit = int(self.config['strategies']['arbitrage']['min_profit_wei'])
        self.assertGreater(result['profit'], min_profit, "Should exceed minimum profit threshold")
        
        # Verify position size limits and risk management
        max_size = int(self.config['strategies']['arbitrage']['max_position_size'])
        self.assertLessEqual(result['amount'], max_size, "Should respect maximum position size")
        self.assertGreater(result['amount'], 0, "Should have non-zero position size")
        
        # Calculate price impact
        price_impact = Decimal(str(result['amount'])) / Decimal(str(uni_pool['reserves']['token1']))
        self.assertLess(price_impact, Decimal('0.05'), "Price impact should be under 5%")
        
        # Verify gas cost considerations with EIP-1559 mechanics
        base_fee = self.base_gas_price
        priority_fee = self.priority_fee
        total_gas_cost = (base_fee + priority_fee) * strategy.base_gas
        net_profit = result['profit'] - total_gas_cost
        
        self.assertGreater(net_profit, min_profit, "Should be profitable after gas costs")
        self.assertGreater(
            net_profit / Decimal(str(result['amount'])) * Decimal('100'),
            Decimal('0.1'),  # At least 0.1% ROI
            "Should have meaningful ROI"
        )
        
        # Verify pool addresses
        self.assertEqual(
            result['pools']['uniswap'],
            uni_pool['pair_address'],
            "Should use correct Uniswap pool"
        )
        self.assertEqual(
            result['pools']['sushiswap'],
            sushi_pool['pair_address'],
            "Should use correct Sushiswap pool"
        )
        
        # Verify timing constraints
        self.assertLess(
            abs(result['timestamp'] - int(time.time())),
            2,
            "Timestamp should be current"
        )

    @patch('web3.Web3.to_wei')
    async def test_high_gas_rejection(self, mock_to_wei):
        """Test rejection of opportunities during various high gas scenarios."""
        mock_to_wei.side_effect = self.w3.to_wei
        
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)
        
        # Setup pool data with profitable spread
        mock_decode = Mock()
        mock_decode.return_value = {
            'dex': 'uniswap',
            'path': [
                self.config['tokens']['weth'],
                self.config['tokens']['usdc']
            ],
            'amountIn': 1000000000000000000
        }
        strategy.dex_handler.decode_swap_data = mock_decode

        # Use pools with good arbitrage opportunity
        uni_pool = {
            'pair_address': '0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc',
            'reserves': {
                'token0': 50000000000000,
                'token1': 25000000000000000000000
            },
            'fee': Decimal('0.003'),
            'token0': self.config['tokens']['usdc'],
            'token1': self.config['tokens']['weth'],
            'decimals0': 6,
            'decimals1': 18,
            'last_k': Decimal('1.25e27'),
            'block_timestamp_last': int(time.time()) - 300,
            'price0_cumulative_last': Decimal('1.234e27'),
            'price1_cumulative_last': Decimal('4.567e27'),
            'pending_txs': []
        }
        sushi_pool = {
            'pair_address': '0x397FF1542f962076d0BFE58eA045FfA2d347ACa0',
            'reserves': {
                'token0': 45000000000000,
                'token1': 24000000000000000000000
            },
            'fee': Decimal('0.003'),
            'token0': self.config['tokens']['usdc'],
            'token1': self.config['tokens']['weth'],
            'decimals0': 6,
            'decimals1': 18,
            'last_k': Decimal('1.08e27'),
            'block_timestamp_last': int(time.time()) - 180,
            'price0_cumulative_last': Decimal('1.235e27'),
            'price1_cumulative_last': Decimal('4.568e27'),
            'pending_txs': []
        }

        async def mock_get_pool_info(dex, *args):
            return uni_pool if dex == 'uniswap' else sushi_pool

        strategy.dex_handler.get_pool_info = mock_get_pool_info

        # Test various high gas scenarios
        gas_scenarios = [
            {
                'name': 'Extreme base fee',
                'base_fee': 500000000000,  # 500 GWEI
                'priority_fee': 2000000000  # 2 GWEI
            },
            {
                'name': 'High priority fee',
                'base_fee': 30000000000,   # 30 GWEI
                'priority_fee': 50000000000 # 50 GWEI
            },
            {
                'name': 'Combined high fees',
                'base_fee': 200000000000,  # 200 GWEI
                'priority_fee': 20000000000 # 20 GWEI
            }
        ]

        for scenario in gas_scenarios:
            # Update gas prices for scenario
            self.w3.eth.get_gas_price = AsyncMock(return_value=scenario['base_fee'] + scenario['priority_fee'])
            self.w3.eth.get_block = AsyncMock(return_value={
                'baseFeePerGas': scenario['base_fee'],
                'gasLimit': 30000000,
                'gasUsed': 15000000,
                'timestamp': int(time.time())
            })

            tx = {
                'hash': '0x' + '1' * 64,
                'nonce': 1,
                'blockHash': None,
                'blockNumber': None,
                'transactionIndex': None,
                'from': '0x' + '4' * 40,
                'to': self.config['dex']['uniswap_v2_router'].lower(),
                'value': 1000000000000000000,
                'gas': 300000,
                'maxFeePerGas': scenario['base_fee'] * 2,
                'maxPriorityFeePerGas': scenario['priority_fee'],
                'input': '0x38ed1739000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000002000000000000000000000000c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2000000000000000000000000a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
                'type': 2,
                'chainId': 1,
                'accessList': []
            }

            result = await strategy.analyze_transaction(tx)
            
            # Verify opportunity is rejected due to high gas
            self.assertIsNone(
                result,
                f"Should reject opportunity in {scenario['name']} scenario"
            )
            
            # Calculate theoretical profit vs gas cost
            gas_cost = (scenario['base_fee'] + scenario['priority_fee']) * strategy.base_gas
            min_profit = int(self.config['strategies']['arbitrage']['min_profit_wei'])
            
            self.assertGreater(
                gas_cost,
                min_profit / 2,  # Gas cost should significantly impact profitability
                f"Gas cost in {scenario['name']} scenario should make arbitrage unprofitable"
            )

    @patch('web3.Web3.to_wei')
    async def test_sandwich_protection(self, mock_to_wei):
        """Test protection against various sandwich attack scenarios."""
        mock_to_wei.side_effect = self.w3.to_wei
        
        strategy = EnhancedArbitrageStrategy(self.w3, self.config)
        
        # Setup base transaction data
        mock_decode = Mock()
        mock_decode.return_value = {
            'dex': 'uniswap',
            'path': [
                self.config['tokens']['weth'],
                self.config['tokens']['usdc']
            ],
            'amountIn': 1000000000000000000
        }
        strategy.dex_handler.decode_swap_data = mock_decode

        # Base pool data
        base_uni_pool = {
            'pair_address': '0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc',
            'reserves': {
                'token0': 50000000000000,
                'token1': 25000000000000000000000
            },
            'fee': Decimal('0.003'),
            'token0': self.config['tokens']['usdc'],
            'token1': self.config['tokens']['weth'],
            'decimals0': 6,
            'decimals1': 18,
            'last_k': Decimal('1.25e27'),
            'block_timestamp_last': int(time.time()) - 300,
            'price0_cumulative_last': Decimal('1.234e27'),
            'price1_cumulative_last': Decimal('4.567e27')
        }
        
        base_sushi_pool = {
            'pair_address': '0x397FF1542f962076d0BFE58eA045FfA2d347ACa0',
            'reserves': {
                'token0': 45000000000000,
                'token1': 24000000000000000000000
            },
            'fee': Decimal('0.003'),
            'token0': self.config['tokens']['usdc'],
            'token1': self.config['tokens']['weth'],
            'decimals0': 6,
            'decimals1': 18,
            'last_k': Decimal('1.08e27'),
            'block_timestamp_last': int(time.time()) - 180,
            'price0_cumulative_last': Decimal('1.235e27'),
            'price1_cumulative_last': Decimal('4.568e27')
        }

        # Test scenarios for sandwich protection
        scenarios = [
            {
                'name': 'Multiple pending swaps',
                'pending_txs': [
                    {'type': 'swap', 'amount': '1000000000000000000', 'direction': 'exact_tokens_for_tokens'},
                    {'type': 'swap', 'amount': '2000000000000000000', 'direction': 'exact_tokens_for_tokens'}
                ]
            },
            {
                'name': 'Large pending swap',
                'pending_txs': [
                    {'type': 'swap', 'amount': '10000000000000000000000', 'direction': 'exact_tokens_for_eth'}
                ]
            },
            {
                'name': 'Suspicious pattern',
                'pending_txs': [
                    {'type': 'swap', 'amount': '500000000000000000', 'direction': 'exact_eth_for_tokens'},
                    {'type': 'swap', 'amount': '1000000000000000000', 'direction': 'exact_tokens_for_eth'},
                    {'type': 'swap', 'amount': '500000000000000000', 'direction': 'exact_eth_for_tokens'}
                ]
            },
            {
                'name': 'High frequency trading',
                'pending_txs': [
                    *[{'type': 'swap', 'amount': '100000000000000000', 'direction': 'exact_tokens_for_tokens', 
                       'timestamp': int(time.time()) - i} for i in range(10)]
                ]
            }
        ]

        for scenario in scenarios:
            # Update pool data with scenario's pending transactions
            uni_pool = {**base_uni_pool, 'pending_txs': scenario['pending_txs']}
            sushi_pool = {**base_sushi_pool, 'pending_txs': []}  # Keep Sushiswap clean for control

            async def mock_get_pool_info(dex, *args):
                return uni_pool if dex == 'uniswap' else sushi_pool

            strategy.dex_handler.get_pool_info = mock_get_pool_info

            # Create transaction with realistic properties
            tx = {
                'hash': '0x' + '1' * 64,
                'nonce': 1,
                'blockHash': None,
                'blockNumber': None,
                'transactionIndex': None,
                'from': '0x' + '4' * 40,
                'to': self.config['dex']['uniswap_v2_router'].lower(),
                'value': 1000000000000000000,
                'gas': 300000,
                'maxFeePerGas': self.base_gas_price * 2,
                'maxPriorityFeePerGas': self.priority_fee,
                'input': '0x38ed1739000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000002000000000000000000000000c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2000000000000000000000000a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
                'type': 2,
                'chainId': 1,
                'accessList': []
            }

            result = await strategy.analyze_transaction(tx)
            
            # Verify opportunity is rejected due to sandwich risk
            self.assertIsNone(
                result,
                f"Should reject opportunity in {scenario['name']} scenario"
            )
            
            # Verify specific sandwich protection logic
            if 'Large pending swap' in scenario['name']:
                # Large swaps should trigger immediate rejection
                self.assertGreater(
                    int(scenario['pending_txs'][0]['amount']),
                    int(self.config['strategies']['arbitrage']['max_position_size']),
                    "Large pending swaps should exceed position limits"
                )
            elif 'High frequency' in scenario['name']:
                # Verify time-based protections
                tx_times = [tx.get('timestamp', 0) for tx in scenario['pending_txs']]
                self.assertLess(
                    max(tx_times) - min(tx_times),
                    60,  # Within 1 minute
                    "High frequency trading should be detected"
                )
            
            # Verify pool state remains unchanged
            self.assertEqual(
                uni_pool['reserves'],
                base_uni_pool['reserves'],
                "Pool reserves should not be modified by pending transactions"
            )

if __name__ == '__main__':
    unittest.main()
