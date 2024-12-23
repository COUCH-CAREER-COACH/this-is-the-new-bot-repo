"""Contract interaction utilities."""
from typing import Dict, Optional, List, Tuple, Any
from web3 import Web3
import json
import asyncio

from ..logger_config import logger
from ..exceptions import (
    ContractError,
    ValidationError,
    SecurityError
)

class ContractHandler:
    """Handles contract interactions and validations."""
    
    def __init__(self, w3: Web3, config: Dict[str, Any]):
        """Initialize contract handler."""
        self.w3 = w3
        self.config = config
        
        try:
            # Load contract ABIs
            self.erc20_abi = self._load_abi('contracts/interfaces/IERC20.json')
            self.flash_loan_abi = self._load_abi('contracts/FlashLoanArbitrage.json')
            
            # Initialize contract addresses
            self.flash_loan_address = self.w3.to_checksum_address(
                config.get('contract_address')
            )
            
            logger.info("Contract handler initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing contract handler: {e}")
            raise ContractError(f"Failed to initialize contract handler: {e}")

    def _load_abi(self, path: str) -> List[Dict]:
        """Load contract ABI from file."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise ContractError(f"Failed to load ABI from {path}: {e}")

    async def validate_contract(
        self,
        address: str,
        abi: List[Dict]
    ) -> bool:
        """Validate contract implementation."""
        try:
            # Check if address is a contract
            code = await self.w3.eth.get_code(address)
            if code == b'' or code == '0x':
                raise ContractError(f"No contract code at address {address}")
                
            # Get contract instance
            contract = self.w3.eth.contract(
                address=address,
                abi=abi
            )
            
            # Verify contract interface
            for item in abi:
                if item['type'] == 'function':
                    if not hasattr(contract.functions, item['name']):
                        raise ContractError(
                            f"Contract missing function: {item['name']}"
                        )
                        
            return True
            
        except Exception as e:
            logger.error(f"Error validating contract: {e}")
            return False

    async def verify_contract_code(
        self,
        address: str,
        expected_bytecode: str
    ) -> bool:
        """Verify contract bytecode matches expected."""
        try:
            deployed_code = await self.w3.eth.get_code(address)
            deployed_code_hex = deployed_code.hex()
            
            # Remove metadata hash from comparison
            deployed_code_no_meta = deployed_code_hex[:-86]
            expected_code_no_meta = expected_bytecode[:-86]
            
            return deployed_code_no_meta == expected_code_no_meta
            
        except Exception as e:
            logger.error(f"Error verifying contract code: {e}")
            return False

    async def estimate_function_gas(
        self,
        contract_address: str,
        abi: List[Dict],
        function_name: str,
        *args: Any
    ) -> int:
        """Estimate gas for contract function call."""
        try:
            contract = self.w3.eth.contract(
                address=contract_address,
                abi=abi
            )
            
            # Get function
            func = getattr(contract.functions, function_name)
            
            # Estimate gas
            gas_estimate = await func(*args).estimate_gas({
                'from': self.w3.eth.default_account
            })
            
            # Add safety margin
            return int(gas_estimate * 1.1)  # 10% buffer
            
        except Exception as e:
            logger.error(f"Error estimating function gas: {e}")
            raise ContractError(f"Failed to estimate gas: {e}")

    async def simulate_function_call(
        self,
        contract_address: str,
        abi: List[Dict],
        function_name: str,
        *args: Any
    ) -> Tuple[bool, Any]:
        """Simulate contract function call."""
        try:
            contract = self.w3.eth.contract(
                address=contract_address,
                abi=abi
            )
            
            # Get function
            func = getattr(contract.functions, function_name)
            
            # Call function (simulation)
            result = await func(*args).call({
                'from': self.w3.eth.default_account
            })
            
            return True, result
            
        except Exception as e:
            logger.error(f"Error simulating function call: {e}")
            return False, str(e)

    async def decode_function_data(
        self,
        abi: List[Dict],
        data: str
    ) -> Optional[Dict]:
        """Decode function call data."""
        try:
            # Create temporary contract
            contract = self.w3.eth.contract(abi=abi)
            
            # Decode function data
            func_obj, decoded_params = contract.decode_function_input(data)
            
            return {
                'function': func_obj.fn_name,
                'params': decoded_params
            }
            
        except Exception as e:
            logger.error(f"Error decoding function data: {e}")
            return None

    async def encode_function_data(
        self,
        abi: List[Dict],
        function_name: str,
        *args: Any
    ) -> str:
        """Encode function call data."""
        try:
            # Create temporary contract
            contract = self.w3.eth.contract(abi=abi)
            
            # Get function
            func = getattr(contract.functions, function_name)
            
            # Encode function call
            return func(*args).build_transaction({
                'gas': 0,
                'gasPrice': 0,
                'nonce': 0,
                'value': 0
            })['data']
            
        except Exception as e:
            logger.error(f"Error encoding function data: {e}")
            raise ContractError(f"Failed to encode function data: {e}")

    async def monitor_contract_events(
        self,
        contract_address: str,
        abi: List[Dict],
        event_names: Optional[List[str]] = None,
        callback: Any = None
    ) -> None:
        """Monitor contract events."""
        try:
            contract = self.w3.eth.contract(
                address=contract_address,
                abi=abi
            )
            
            # Create event filters
            filters = []
            for event_name in (event_names or []):
                if hasattr(contract.events, event_name):
                    event_filter = contract.events[event_name].create_filter(
                        fromBlock='latest'
                    )
                    filters.append((event_name, event_filter))
                    
            # Monitor events
            while True:
                for event_name, event_filter in filters:
                    try:
                        events = event_filter.get_new_entries()
                        for event in events:
                            # Log event
                            logger.info(
                                f"Contract event: {event_name}\n"
                                f"Args: {dict(event.args)}\n"
                                f"Block: {event.blockNumber}"
                            )
                            
                            # Call callback if provided
                            if callback:
                                await callback(event)
                                
                    except Exception as e:
                        logger.error(f"Error processing {event_name} events: {e}")
                        
                await asyncio.sleep(1)  # Poll interval
                
        except Exception as e:
            logger.error(f"Error monitoring contract events: {e}")
            raise ContractError(f"Failed to monitor events: {e}")

    async def verify_contract_state(
        self,
        contract_address: str,
        abi: List[Dict],
        state_checks: Dict[str, Any]
    ) -> bool:
        """Verify contract state matches expected values."""
        try:
            contract = self.w3.eth.contract(
                address=contract_address,
                abi=abi
            )
            
            # Check each state variable
            for var_name, expected_value in state_checks.items():
                if hasattr(contract.functions, var_name):
                    actual_value = await getattr(
                        contract.functions,
                        var_name
                    )().call()
                    
                    if actual_value != expected_value:
                        logger.warning(
                            f"State mismatch for {var_name}: "
                            f"expected {expected_value}, got {actual_value}"
                        )
                        return False
                        
            return True
            
        except Exception as e:
            logger.error(f"Error verifying contract state: {e}")
            return False

    async def check_contract_permissions(
        self,
        contract_address: str,
        abi: List[Dict],
        required_permissions: List[str]
    ) -> bool:
        """Check if contract has required permissions."""
        try:
            contract = self.w3.eth.contract(
                address=contract_address,
                abi=abi
            )
            
            # Check each required permission
            for permission in required_permissions:
                try:
                    # Try to call permission check function
                    has_permission = await getattr(
                        contract.functions,
                        f"has{permission}"
                    )().call()
                    
                    if not has_permission:
                        logger.warning(
                            f"Missing required permission: {permission}"
                        )
                        return False
                        
                except Exception:
                    logger.warning(
                        f"Unable to verify permission: {permission}"
                    )
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error checking contract permissions: {e}")
            return False

    async def validate_contract_upgrade(
        self,
        old_address: str,
        new_address: str,
        abi: List[Dict]
    ) -> bool:
        """Validate contract upgrade maintains required functionality."""
        try:
            # Validate both contracts
            old_valid = await self.validate_contract(old_address, abi)
            new_valid = await self.validate_contract(new_address, abi)
            
            if not old_valid or not new_valid:
                return False
                
            # Compare state variables
            old_contract = self.w3.eth.contract(
                address=old_address,
                abi=abi
            )
            new_contract = self.w3.eth.contract(
                address=new_address,
                abi=abi
            )
            
            # Check each function in ABI
            for item in abi:
                if item['type'] == 'function' and item.get('stateMutability') == 'view':
                    try:
                        old_value = await getattr(
                            old_contract.functions,
                            item['name']
                        )().call()
                        new_value = await getattr(
                            new_contract.functions,
                            item['name']
                        )().call()
                        
                        if old_value != new_value:
                            logger.warning(
                                f"State mismatch after upgrade: {item['name']}"
                            )
                            return False
                            
                    except Exception as e:
                        logger.error(
                            f"Error comparing {item['name']}: {e}"
                        )
                        return False
                        
            return True
            
        except Exception as e:
            logger.error(f"Error validating contract upgrade: {e}")
            return False
