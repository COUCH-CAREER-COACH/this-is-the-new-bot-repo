"""Base strategy class for MEV strategies."""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
from web3 import Web3
from eth_account.account import Account
from decimal import Decimal

from .logger_config import logger
from .exceptions import (
    ConfigurationError,
    InsufficientLiquidityError,
    ExcessiveSlippageError,
    GasEstimationError,
    ContractError
)

class MEVStrategy(ABC):
    """Abstract base class for MEV strategies."""
    
    def __init__(self, w3: Web3, config: Dict[str, Any]):
        """Initialize base strategy with web3 instance and configuration."""
        self.web3 = w3
        self.config = config
        
        try:
            # Load account
            private_key = config['accounts']['mainnet']['private_key']
            self.account = Account.from_key(private_key)
            
            # Load contract address
            self.contract_address = self.web3.to_checksum_address(
                config.get('contract_address')
            )
            
            # Load risk parameters
            risk_config = config.get('risk', {})
            self.max_slippage = Decimal(str(risk_config.get('max_slippage', '0.02')))
            self.min_liquidity = int(risk_config.get('min_liquidity', '1000000000000000000'))
            
            # Load gas parameters
            gas_config = config.get('gas', {})
            self.max_gas_price = int(gas_config.get('max_gas_price', '500000000000'))
            self.priority_fee = int(gas_config.get('priority_fee', '2000000000'))
            
            logger.info(f"Initialized {self.__class__.__name__} strategy")
            
        except Exception as e:
            logger.error(f"Error initializing base strategy: {e}")
            raise ConfigurationError(f"Failed to initialize base strategy: {e}")

    @abstractmethod
    async def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze transaction for MEV opportunity."""
        pass

    @abstractmethod
    async def execute_opportunity(self, opportunity: Dict) -> bool:
        """Execute MEV opportunity."""
        pass

    def _encode_strategy_callback(
        self,
        strategy_type: str,
        token_in: str,
        token_out: str,
        amount: int,
        uni_pool: str,
        sushi_pool: Optional[str] = None
    ) -> bytes:
        """Encode strategy callback data."""
        try:
            # Create function signature based on strategy type
            if strategy_type == 'arbitrage':
                function_signature = 'executeArbitrage(address,address,uint256,address,address)'
                encoded_data = self.web3.eth.contract(
                    abi=[{
                        'inputs': [
                            {'type': 'address', 'name': 'tokenIn'},
                            {'type': 'address', 'name': 'tokenOut'},
                            {'type': 'uint256', 'name': 'amount'},
                            {'type': 'address', 'name': 'uniPool'},
                            {'type': 'address', 'name': 'sushiPool'}
                        ],
                        'name': 'executeArbitrage',
                        'outputs': [],
                        'stateMutability': 'nonpayable',
                        'type': 'function'
                    }]
                ).encodeABI(
                    fn_name='executeArbitrage',
                    args=[token_in, token_out, amount, uni_pool, sushi_pool or uni_pool]
                )
            else:
                raise ValueError(f"Unsupported strategy type: {strategy_type}")
                
            return encoded_data
            
        except Exception as e:
            logger.error(f"Error encoding strategy callback: {e}")
            raise ContractError(f"Failed to encode strategy callback: {e}")

    async def _execute_with_flash_loan(
        self,
        token: str,
        amount: int,
        callback_data: bytes
    ) -> bool:
        """Execute strategy using flash loan."""
        try:
            # Prepare transaction
            contract = self.web3.eth.contract(
                address=self.contract_address,
                abi=[{
                    'inputs': [
                        {'type': 'address', 'name': 'token'},
                        {'type': 'uint256', 'name': 'amount'},
                        {'type': 'bytes', 'name': 'params'}
                    ],
                    'name': 'executeOperation',
                    'outputs': [],
                    'stateMutability': 'nonpayable',
                    'type': 'function'
                }]
            )
            
            # Build transaction
            tx = await contract.functions.executeOperation(
                token,
                amount,
                callback_data
            ).build_transaction({
                'from': self.account.address,
                'gas': 500000,  # Estimated gas limit
                'maxFeePerGas': self.max_gas_price,
                'maxPriorityFeePerGas': self.priority_fee,
                'nonce': await self.web3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send transaction
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = await self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
            success = receipt['status'] == 1
            
            if success:
                logger.info(f"Flash loan execution successful: {tx_hash.hex()}")
            else:
                logger.error(f"Flash loan execution failed: {tx_hash.hex()}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error executing flash loan: {e}")
            return False

    async def validate_pool_liquidity(
        self,
        token_in: str,
        token_out: str,
        amount: int
    ) -> bool:
        """Validate pool has sufficient liquidity."""
        try:
            # Get pool reserves
            pool_contract = self.web3.eth.contract(
                address=self.contract_address,
                abi=[{
                    'inputs': [],
                    'name': 'getReserves',
                    'outputs': [
                        {'type': 'uint112', 'name': 'reserve0'},
                        {'type': 'uint112', 'name': 'reserve1'},
                        {'type': 'uint32', 'name': 'blockTimestampLast'}
                    ],
                    'stateMutability': 'view',
                    'type': 'function'
                }]
            )
            
            reserves = await pool_contract.functions.getReserves().call()
            
            # Check if pool has minimum liquidity
            if reserves[0] < self.min_liquidity or reserves[1] < self.min_liquidity:
                return False
                
            # Check if amount is too large relative to reserves
            if amount > reserves[0] * Decimal('0.1') or amount > reserves[1] * Decimal('0.1'):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating pool liquidity: {e}")
            return False

    async def estimate_gas_cost(self, tx: Dict) -> int:
        """Estimate gas cost for transaction."""
        try:
            gas_estimate = await self.web3.eth.estimate_gas(tx)
            gas_price = await self.web3.eth.gas_price
            
            return gas_estimate * gas_price
            
        except Exception as e:
            logger.error(f"Error estimating gas cost: {e}")
            raise GasEstimationError(f"Failed to estimate gas cost: {e}")
