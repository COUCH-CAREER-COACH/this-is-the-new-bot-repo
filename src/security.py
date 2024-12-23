import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal
from web3 import Web3
from web3.contract import Contract
import json
import time
import eth_abi
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from web3.exceptions import ContractLogicError

logger = logging.getLogger(__name__)

class SecurityManager:
    def __init__(self, web3: Web3, config: Dict):
        """Initialize security management system."""
        self.w3 = web3
        self.config = config['security']
        self.pending_txs = {}
        self.approved_tokens = {}
        self.nonce_tracker = {}
        
        # Initialize flashbots if enabled
        self.flashbots_enabled = self.config.get('flashbots_enabled', False)
        if self.flashbots_enabled:
            from flashbots import flashbot
            self.flashbots = flashbot(self.w3, Account.from_key(config['flashbots']['private_key']))
            logger.info("Flashbots integration enabled")
        
        logger.info("Security management system initialized")

    async def validate_transaction(self, tx: Dict) -> bool:
        """Validate transaction parameters and security checks."""
        try:
            # Check if we have too many pending transactions
            if len(self.pending_txs) >= self.config['max_pending_transactions']:
                logger.warning("Too many pending transactions")
                return False
            
            # Validate basic transaction parameters
            if not self._validate_tx_params(tx):
                return False
            
            # Check if transaction simulation is required
            if self.config['simulate_before_execute']:
                if not await self._simulate_transaction(tx):
                    return False
            
            # Validate token approvals if needed
            if tx.get('requires_approval'):
                if not await self._validate_token_approval(tx):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating transaction: {e}")
            return False

    def _validate_tx_params(self, tx: Dict) -> bool:
        """Validate basic transaction parameters."""
        try:
            # Check required fields
            required_fields = ['to', 'value', 'gas']
            if not all(field in tx for field in required_fields):
                logger.error("Missing required transaction fields")
                return False
            
            # Validate addresses
            if not Web3.is_address(tx['to']):
                logger.error(f"Invalid 'to' address: {tx['to']}")
                return False
            
            # Validate value
            if not isinstance(tx['value'], (int, str)) or int(tx['value']) < 0:
                logger.error(f"Invalid transaction value: {tx['value']}")
                return False
            
            # Validate gas
            if not isinstance(tx['gas'], (int, str)) or int(tx['gas']) <= 0:
                logger.error(f"Invalid gas limit: {tx['gas']}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating transaction parameters: {e}")
            return False

    async def _simulate_transaction(self, tx: Dict) -> bool:
        """Simulate transaction execution."""
        try:
            # Create transaction for simulation
            sim_tx = {
                'from': self.w3.eth.default_account,
                'to': Web3.to_checksum_address(tx['to']),
                'value': int(tx['value']),
                'gas': int(tx['gas']),
                'gasPrice': await self._get_gas_price(),
                'nonce': await self._get_nonce(),
                'data': tx.get('data', '0x')
            }
            
            # Simulate transaction
            try:
                result = await self.w3.eth.call(sim_tx)
                logger.debug(f"Transaction simulation successful: {result.hex()}")
                return True
            except ContractLogicError as e:
                logger.warning(f"Transaction simulation failed: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error simulating transaction: {e}")
            return False

    async def _validate_token_approval(self, tx: Dict) -> bool:
        """Validate and handle token approvals."""
        try:
            token_address = tx.get('token_address')
            spender = tx.get('spender')
            amount = tx.get('amount')
            
            if not all([token_address, spender, amount]):
                logger.error("Missing token approval parameters")
                return False
            
            # Check existing approval
            token = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=self._get_erc20_abi()
            )
            
            current_allowance = await token.functions.allowance(
                self.w3.eth.default_account,
                Web3.to_checksum_address(spender)
            ).call()
            
            if current_allowance >= int(amount):
                return True
            
            # Revoke existing approval if configured
            if self.config['revoke_approvals_after'] and current_allowance > 0:
                await self._revoke_token_approval(token, spender)
            
            # Set new approval
            approval_amount = self.config['max_approval_amount']
            approval_tx = await token.functions.approve(
                Web3.to_checksum_address(spender),
                int(approval_amount)
            ).build_transaction({
                'from': self.w3.eth.default_account,
                'gas': 100000,
                'gasPrice': await self._get_gas_price(),
                'nonce': await self._get_nonce()
            })
            
            # Send approval transaction
            signed_tx = self.w3.eth.account.sign_transaction(
                approval_tx,
                private_key=self.w3.eth.account.default_account.privateKey
            )
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt['status'] != 1:
                logger.error("Token approval failed")
                return False
            
            logger.info(f"Token approval successful: {tx_hash.hex()}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling token approval: {e}")
            return False

    async def execute_transaction(self, tx: Dict) -> Tuple[bool, Optional[str]]:
        """Execute transaction with security measures."""
        try:
            # Validate transaction first
            if not await self.validate_transaction(tx):
                return False, None
            
            # Prepare transaction
            tx_params = await self._prepare_transaction(tx)
            
            # Use flashbots if enabled
            if self.flashbots_enabled and self.config.get('private_transactions', False):
                return await self._send_via_flashbots(tx_params)
            
            # Regular transaction execution
            signed_tx = self.w3.eth.account.sign_transaction(
                tx_params,
                private_key=self.w3.eth.account.default_account.privateKey
            )
            
            # Send transaction
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            self.pending_txs[tx_hash.hex()] = time.time()
            
            logger.info(f"Transaction sent: {tx_hash.hex()}")
            return True, tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Error executing transaction: {e}")
            return False, None

    async def _send_via_flashbots(self, tx_params: Dict) -> Tuple[bool, Optional[str]]:
        """Send transaction via Flashbots."""
        try:
            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(
                tx_params,
                private_key=self.w3.eth.account.default_account.privateKey
            )
            
            # Create flashbots bundle
            bundle = [
                {
                    "signed_transaction": signed_tx.rawTransaction
                }
            ]
            
            # Simulate bundle
            simulation = await self.flashbots.simulate(bundle, block_tag='latest')
            if not simulation['success']:
                logger.warning(f"Flashbots simulation failed: {simulation}")
                return False, None
            
            # Send bundle
            block = await self.w3.eth.block_number
            result = await self.flashbots.send_bundle(
                bundle,
                target_block_number=block + 1
            )
            
            bundle_hash = result.bundle_hash()
            logger.info(f"Flashbots bundle sent: {bundle_hash}")
            
            # Wait for inclusion
            inclusion = await result.wait()
            if inclusion:
                logger.info(f"Bundle included in block {inclusion['block_number']}")
                return True, bundle_hash
            else:
                logger.warning("Bundle not included")
                return False, None
                
        except Exception as e:
            logger.error(f"Error sending via Flashbots: {e}")
            return False, None

    async def _prepare_transaction(self, tx: Dict) -> Dict:
        """Prepare transaction parameters."""
        return {
            'from': self.w3.eth.default_account,
            'to': Web3.to_checksum_address(tx['to']),
            'value': int(tx['value']),
            'gas': int(tx['gas']),
            'gasPrice': await self._get_gas_price(),
            'nonce': await self._get_nonce(),
            'data': tx.get('data', '0x')
        }

    async def _get_gas_price(self) -> int:
        """Get current gas price with safety checks."""
        try:
            gas_price = self.w3.eth.gas_price
            max_gas = int(self.config.get('max_gas_price', '100000000000'))
            return min(gas_price, max_gas)
        except Exception as e:
            logger.error(f"Error getting gas price: {e}")
            return 0

    async def _get_nonce(self) -> int:
        """Get next nonce with tracking."""
        try:
            address = self.w3.eth.default_account
            network_nonce = await self.w3.eth.get_transaction_count(address, 'pending')
            tracked_nonce = self.nonce_tracker.get(address, network_nonce)
            next_nonce = max(network_nonce, tracked_nonce)
            self.nonce_tracker[address] = next_nonce + 1
            return next_nonce
        except Exception as e:
            logger.error(f"Error getting nonce: {e}")
            return 0

    async def _revoke_token_approval(self, token: Contract, spender: str):
        """Revoke token approval."""
        try:
            revoke_tx = await token.functions.approve(
                Web3.to_checksum_address(spender),
                0
            ).build_transaction({
                'from': self.w3.eth.default_account,
                'gas': 100000,
                'gasPrice': await self._get_gas_price(),
                'nonce': await self._get_nonce()
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(
                revoke_tx,
                private_key=self.w3.eth.account.default_account.privateKey
            )
            
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] != 1:
                logger.error("Failed to revoke token approval")
            else:
                logger.info(f"Token approval revoked: {tx_hash.hex()}")
                
        except Exception as e:
            logger.error(f"Error revoking token approval: {e}")

    def _get_erc20_abi(self) -> list:
        """Get basic ERC20 ABI."""
        return [
            {
                "constant": True,
                "inputs": [
                    {
                        "name": "owner",
                        "type": "address"
                    },
                    {
                        "name": "spender",
                        "type": "address"
                    }
                ],
                "name": "allowance",
                "outputs": [
                    {
                        "name": "",
                        "type": "uint256"
                    }
                ],
                "payable": False,
                "stateMutability": "view",
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {
                        "name": "spender",
                        "type": "address"
                    },
                    {
                        "name": "amount",
                        "type": "uint256"
                    }
                ],
                "name": "approve",
                "outputs": [
                    {
                        "name": "",
                        "type": "bool"
                    }
                ],
                "payable": False,
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]

    def cleanup_pending_transactions(self):
        """Clean up old pending transactions."""
        now = time.time()
        expired = []
        for tx_hash, timestamp in self.pending_txs.items():
            if now - timestamp > 3600:  # 1 hour timeout
                expired.append(tx_hash)
        
        for tx_hash in expired:
            del self.pending_txs[tx_hash]
