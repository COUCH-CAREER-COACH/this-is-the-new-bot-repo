"""Flashbots interaction module."""
from typing import Dict, Optional, List, Any, Union
from decimal import Decimal
from web3 import Web3
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
import json
import time
import requests
import asyncio

from .logger_config import logger
from .exceptions import (
    FlashbotsError,
    ValidationError,
    NetworkError
)

class FlashbotsManager:
    """Manages Flashbots bundle creation and submission."""
    
    def __init__(
        self,
        w3: Web3,
        private_key: str,
        relay_url: str,
        auth_key: Optional[str] = None
    ):
        """Initialize Flashbots manager."""
        self.w3 = w3
        self.account: LocalAccount = Account.from_key(private_key)
        self.relay_url = relay_url
        self.auth_key = auth_key or private_key
        
        try:
            # Initialize session
            self.session = requests.Session()
            self.session.headers.update({
                'Content-Type': 'application/json',
                'X-Flashbots-Signature': self._get_auth_header()
            })
            
            # Initialize state
            self.pending_bundles: Dict[str, Dict] = {}
            self.simulation_results: Dict[str, Dict] = {}
            self.last_block = 0
            
            logger.info("Flashbots manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Flashbots manager: {e}")
            raise FlashbotsError(f"Failed to initialize Flashbots manager: {e}")

    def _get_auth_header(self) -> str:
        """Get authentication header for Flashbots relay."""
        try:
            message = "flashbots " + str(int(time.time()))
            signed = Account.sign_message(
                message.encode('utf-8'),
                self.auth_key
            )
            return f"{self.account.address}:{signed.signature.hex()}"
            
        except Exception as e:
            logger.error(f"Error creating auth header: {e}")
            raise FlashbotsError(f"Failed to create auth header: {e}")

    async def create_bundle(
        self,
        transactions: List[Dict[str, Any]],
        target_block: Optional[Union[int, str]] = None,
        simulation_timestamp: Optional[int] = None
    ) -> str:
        """Create a new transaction bundle."""
        try:
            # Validate transactions
            if not self._validate_transactions(transactions):
                raise ValidationError("Invalid transactions in bundle")
                
            # Get target block
            if target_block is None or target_block == '+1':
                target_block = self.w3.eth.block_number + 1
            elif target_block == '+2':
                target_block = self.w3.eth.block_number + 2
                
            # Generate bundle ID
            bundle_id = f"bundle_{target_block}_{int(time.time())}"
            
            # Store bundle
            self.pending_bundles[bundle_id] = {
                'transactions': transactions,
                'target_block': target_block,
                'simulation_timestamp': simulation_timestamp or int(time.time()),
                'status': 'pending',
                'attempts': 0,
                'created_at': time.time()
            }
            
            return bundle_id
            
        except Exception as e:
            logger.error(f"Error creating bundle: {e}")
            raise FlashbotsError(f"Failed to create bundle: {e}")

    def _validate_transactions(self, transactions: List[Dict[str, Any]]) -> bool:
        """Validate transaction bundle."""
        try:
            if not transactions:
                return False
                
            for tx in transactions:
                # Check required fields
                required_fields = ['to', 'value', 'gas', 'maxFeePerGas', 'maxPriorityFeePerGas']
                if not all(field in tx for field in required_fields):
                    return False
                    
                # Validate addresses
                if not self.w3.is_address(tx['to']):
                    return False
                    
                # Validate gas values
                if tx['gas'] <= 0 or tx['maxFeePerGas'] <= 0:
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error validating transactions: {e}")
            return False

    async def simulate_bundle(self, bundle_id: str) -> Dict[str, Any]:
        """Simulate bundle execution."""
        try:
            bundle = self.pending_bundles.get(bundle_id)
            if not bundle:
                raise FlashbotsError(f"Bundle not found: {bundle_id}")
                
            # Prepare simulation request
            simulation_request = {
                'txs': [
                    self._prepare_transaction(tx)
                    for tx in bundle['transactions']
                ],
                'blockNumber': hex(bundle['target_block']),
                'timestamp': hex(bundle['simulation_timestamp'])
            }
            
            # Send simulation request
            response = await self._post_request(
                f"{self.relay_url}/simulate",
                simulation_request
            )
            
            # Store simulation results
            self.simulation_results[bundle_id] = response
            
            return response
            
        except Exception as e:
            logger.error(f"Error simulating bundle: {e}")
            raise FlashbotsError(f"Failed to simulate bundle: {e}")

    def _prepare_transaction(self, tx: Dict[str, Any]) -> str:
        """Prepare transaction for Flashbots submission."""
        try:
            # Sign transaction
            signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
            return signed.rawTransaction.hex()
            
        except Exception as e:
            logger.error(f"Error preparing transaction: {e}")
            raise FlashbotsError(f"Failed to prepare transaction: {e}")

    async def submit_bundle(self, bundle_id: str) -> bool:
        """Submit bundle to Flashbots relay."""
        try:
            bundle = self.pending_bundles.get(bundle_id)
            if not bundle:
                raise FlashbotsError(f"Bundle not found: {bundle_id}")
                
            # Prepare submission request
            submission_request = {
                'txs': [
                    self._prepare_transaction(tx)
                    for tx in bundle['transactions']
                ],
                'blockNumber': hex(bundle['target_block'])
            }
            
            # Send submission request
            response = await self._post_request(
                f"{self.relay_url}/bundle",
                submission_request
            )
            
            # Update bundle status
            bundle['status'] = 'submitted'
            bundle['attempts'] += 1
            
            return response.get('submitted', False)
            
        except Exception as e:
            logger.error(f"Error submitting bundle: {e}")
            raise FlashbotsError(f"Failed to submit bundle: {e}")

    async def _post_request(
        self,
        url: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send POST request to Flashbots relay."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.session.post(url, json=data)
            )
            
            if response.status_code != 200:
                raise NetworkError(
                    f"Relay request failed: {response.status_code} - {response.text}"
                )
                
            return response.json()
            
        except Exception as e:
            logger.error(f"Error sending relay request: {e}")
            raise NetworkError(f"Failed to send relay request: {e}")

    async def monitor_bundle(
        self,
        bundle_id: str,
        max_blocks: int = 2
    ) -> Optional[Dict[str, Any]]:
        """Monitor bundle inclusion."""
        try:
            bundle = self.pending_bundles.get(bundle_id)
            if not bundle:
                raise FlashbotsError(f"Bundle not found: {bundle_id}")
                
            start_block = self.w3.eth.block_number
            target_block = bundle['target_block']
            
            while self.w3.eth.block_number <= start_block + max_blocks:
                # Check if target block has passed
                if self.w3.eth.block_number > target_block:
                    bundle['status'] = 'failed'
                    return None
                    
                # Check bundle inclusion
                for tx in bundle['transactions']:
                    try:
                        receipt = self.w3.eth.get_transaction_receipt(tx['hash'])
                        if receipt and receipt['blockNumber'] == target_block:
                            bundle['status'] = 'included'
                            return receipt
                    except Exception:
                        pass
                        
                await asyncio.sleep(1)
                
            bundle['status'] = 'failed'
            return None
            
        except Exception as e:
            logger.error(f"Error monitoring bundle: {e}")
            raise FlashbotsError(f"Failed to monitor bundle: {e}")

    def get_bundle_status(self, bundle_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a bundle."""
        try:
            return self.pending_bundles.get(bundle_id)
        except Exception as e:
            logger.error(f"Error getting bundle status: {e}")
            return None

    def get_simulation_result(self, bundle_id: str) -> Optional[Dict[str, Any]]:
        """Get simulation result for a bundle."""
        try:
            return self.simulation_results.get(bundle_id)
        except Exception as e:
            logger.error(f"Error getting simulation result: {e}")
            return None

    def cleanup(self):
        """Clean up resources."""
        try:
            # Clear pending bundles
            self.pending_bundles.clear()
            self.simulation_results.clear()
            
            # Close session
            self.session.close()
            
        except Exception as e:
            logger.error(f"Error cleaning up Flashbots manager: {e}")
