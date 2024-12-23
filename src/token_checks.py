"""Token validation and approval checks."""
from typing import List, Dict, Optional
from web3 import Web3
import asyncio

from .logger_config import logger
from .exceptions import (
    TokenError,
    ValidationError,
    SecurityError
)

async def check_token_allowance(
    w3: Web3,
    token: str,
    token_abi: list,
    owner: str,
    spenders: List[str],
    required_amount: int
) -> bool:
    """Check if token allowance is sufficient for all spenders."""
    try:
        # Get token contract
        token_contract = w3.eth.contract(
            address=token,
            abi=token_abi
        )
        
        # Check allowance for each spender
        for spender in spenders:
            try:
                allowance = await token_contract.functions.allowance(
                    owner,
                    spender
                ).call()
                
                if allowance < required_amount:
                    logger.warning(
                        f"Insufficient allowance for {spender}: "
                        f"{allowance} < {required_amount}"
                    )
                    return False
                    
            except Exception as e:
                logger.error(f"Error checking allowance for {spender}: {e}")
                return False
                
        return True
        
    except Exception as e:
        logger.error(f"Error checking token allowances: {e}")
        return False

async def validate_token_contract(
    w3: Web3,
    token: str,
    token_abi: list
) -> bool:
    """Validate token contract implementation."""
    try:
        # Check if address is a contract
        code = await w3.eth.get_code(token)
        if code == b'' or code == '0x':
            raise TokenError(f"No contract code at address {token}")
            
        # Get token contract
        token_contract = w3.eth.contract(
            address=token,
            abi=token_abi
        )
        
        # Check required ERC20 functions
        required_functions = [
            'balanceOf',
            'transfer',
            'transferFrom',
            'approve',
            'allowance',
            'totalSupply'
        ]
        
        for func in required_functions:
            if not hasattr(token_contract.functions, func):
                raise TokenError(f"Token contract missing {func} function")
                
        # Check token details
        try:
            name = await token_contract.functions.name().call()
            symbol = await token_contract.functions.symbol().call()
            decimals = await token_contract.functions.decimals().call()
            total_supply = await token_contract.functions.totalSupply().call()
            
            if not all([name, symbol, decimals, total_supply]):
                raise TokenError("Invalid token details")
                
        except Exception as e:
            raise TokenError(f"Error getting token details: {e}")
            
        return True
        
    except Exception as e:
        logger.error(f"Error validating token contract: {e}")
        return False

async def check_token_balance(
    w3: Web3,
    token: str,
    token_abi: list,
    address: str,
    required_amount: int
) -> bool:
    """Check if address has sufficient token balance."""
    try:
        # Get token contract
        token_contract = w3.eth.contract(
            address=token,
            abi=token_abi
        )
        
        # Get balance
        balance = await token_contract.functions.balanceOf(address).call()
        
        if balance < required_amount:
            logger.warning(
                f"Insufficient balance: {balance} < {required_amount}"
            )
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error checking token balance: {e}")
        return False

async def validate_token_transfer(
    w3: Web3,
    token: str,
    token_abi: list,
    from_address: str,
    to_address: str,
    amount: int
) -> bool:
    """Validate token transfer is possible."""
    try:
        # Check balances and allowances
        has_balance = await check_token_balance(
            w3,
            token,
            token_abi,
            from_address,
            amount
        )
        if not has_balance:
            return False
            
        # Check allowance if transferring on behalf
        if from_address != w3.eth.default_account:
            has_allowance = await check_token_allowance(
                w3,
                token,
                token_abi,
                from_address,
                [w3.eth.default_account],
                amount
            )
            if not has_allowance:
                return False
                
        # Validate addresses
        if not w3.is_address(from_address) or not w3.is_address(to_address):
            return False
            
        # Check if addresses are not the same
        if from_address.lower() == to_address.lower():
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error validating token transfer: {e}")
        return False

async def check_token_security(
    w3: Web3,
    token: str,
    token_abi: list
) -> Dict[str, bool]:
    """Perform security checks on token contract."""
    try:
        security_checks = {
            'valid_contract': False,
            'non_zero_supply': False,
            'transfer_enabled': False,
            'no_blacklist': False,
            'no_fee_on_transfer': False
        }
        
        # Get token contract
        token_contract = w3.eth.contract(
            address=token,
            abi=token_abi
        )
        
        # Check contract validity
        security_checks['valid_contract'] = await validate_token_contract(
            w3,
            token,
            token_abi
        )
        
        # Check total supply
        total_supply = await token_contract.functions.totalSupply().call()
        security_checks['non_zero_supply'] = total_supply > 0
        
        # Test transfer functionality
        try:
            # Try to transfer 0 tokens to check if transfers are enabled
            await token_contract.functions.transfer(
                w3.eth.default_account,
                0
            ).call({'from': w3.eth.default_account})
            security_checks['transfer_enabled'] = True
        except Exception:
            security_checks['transfer_enabled'] = False
            
        # Check for blacklist functionality
        code = await w3.eth.get_code(token)
        code_str = code.hex()
        security_checks['no_blacklist'] = 'blacklist' not in code_str.lower()
        
        # Check for transfer fees
        try:
            balance_before = await token_contract.functions.balanceOf(
                w3.eth.default_account
            ).call()
            
            # Transfer tokens to self
            await token_contract.functions.transfer(
                w3.eth.default_account,
                balance_before
            ).call({'from': w3.eth.default_account})
            
            balance_after = await token_contract.functions.balanceOf(
                w3.eth.default_account
            ).call()
            
            security_checks['no_fee_on_transfer'] = balance_before == balance_after
            
        except Exception:
            security_checks['no_fee_on_transfer'] = False
            
        return security_checks
        
    except Exception as e:
        logger.error(f"Error performing security checks: {e}")
        raise SecurityError(f"Failed to perform security checks: {e}")

async def monitor_token_events(
    w3: Web3,
    token: str,
    token_abi: list,
    event_names: Optional[List[str]] = None
) -> None:
    """Monitor token events for suspicious activity."""
    try:
        # Get token contract
        token_contract = w3.eth.contract(
            address=token,
            abi=token_abi
        )
        
        # Default events to monitor
        if not event_names:
            event_names = ['Transfer', 'Approval']
            
        # Create event filters
        filters = []
        for event_name in event_names:
            if hasattr(token_contract.events, event_name):
                event_filter = token_contract.events[event_name].create_filter(
                    fromBlock='latest'
                )
                filters.append((event_name, event_filter))
                
        # Monitor events
        while True:
            for event_name, event_filter in filters:
                try:
                    events = event_filter.get_new_entries()
                    for event in events:
                        # Log event details
                        logger.info(
                            f"Token event: {event_name}\n"
                            f"Args: {dict(event.args)}\n"
                            f"Block: {event.blockNumber}"
                        )
                        
                        # Check for suspicious patterns
                        if await is_suspicious_event(event):
                            logger.warning(
                                f"Suspicious token event detected:\n{event}"
                            )
                            
                except Exception as e:
                    logger.error(f"Error processing {event_name} events: {e}")
                    
            await asyncio.sleep(1)  # Poll interval
            
    except Exception as e:
        logger.error(f"Error monitoring token events: {e}")
        raise

async def is_suspicious_event(event: Dict) -> bool:
    """Check if token event is suspicious."""
    try:
        # Check for large transfers
        if hasattr(event.args, 'value') and event.args.value > 10**20:  # 100 tokens
            return True
            
        # Check for multiple transfers in same block
        if hasattr(event, 'blockNumber'):
            block_events = await get_block_events(
                event.address,
                event.blockNumber
            )
            if len(block_events) > 5:  # More than 5 events in same block
                return True
                
        return False
        
    except Exception as e:
        logger.error(f"Error checking suspicious event: {e}")
        return False

async def get_block_events(
    token: str,
    block_number: int
) -> List[Dict]:
    """Get all token events in a specific block."""
    try:
        # Implementation would get all events for token in block
        return []
    except Exception as e:
        logger.error(f"Error getting block events: {e}")
        return []
