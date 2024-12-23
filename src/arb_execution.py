"""Arbitrage execution module."""
from typing import Dict, Tuple, Callable, Any
from decimal import Decimal
from web3 import Web3
import asyncio

from .logger_config import logger
from .exceptions import (
    ExecutionError,
    TransactionError,
    ValidationError
)
from . import mainnet_helpers as mainnet
from . import token_checks

async def validate_execution_conditions(
    w3: Web3,
    opportunity: Dict,
    min_profit: int,
    max_gas_price: int
) -> bool:
    """Validate conditions before executing arbitrage."""
    try:
        # Validate network connection
        if not await mainnet.validate_network(w3):
            logger.error("Network validation failed")
            return False
            
        # Validate gas price
        current_gas_price = await w3.eth.gas_price
        if current_gas_price > max_gas_price:
            logger.warning(f"Gas price too high: {current_gas_price} > {max_gas_price}")
            return False
            
        # Validate profit after current gas price
        gas_cost = current_gas_price * opportunity['gas_estimate']
        net_profit = opportunity['profit'] - gas_cost
        
        if net_profit < min_profit:
            logger.warning(f"Insufficient profit after gas: {net_profit} < {min_profit}")
            return False
            
        # Validate pool liquidity hasn't changed significantly
        for dex, pool in opportunity['pools'].items():
            if not await validate_pool_liquidity(w3, pool):
                logger.warning(f"Insufficient liquidity in {dex} pool")
                return False
                
        return True
        
    except Exception as e:
        logger.error(f"Error validating execution conditions: {e}")
        return False

async def validate_pool_liquidity(
    w3: Web3,
    pool_address: str
) -> bool:
    """Validate pool liquidity is sufficient."""
    try:
        # Get pool contract
        pool_contract = w3.eth.contract(
            address=pool_address,
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
        
        # Get current reserves
        reserves = await pool_contract.functions.getReserves().call()
        
        # Check minimum liquidity
        return reserves[0] >= mainnet.MIN_LIQUIDITY and reserves[1] >= mainnet.MIN_LIQUIDITY
        
    except Exception as e:
        logger.error(f"Error validating pool liquidity: {e}")
        return False

async def execute_arbitrage(
    w3: Web3,
    opportunity: Dict,
    contract_address: str,
    token_abi: list,
    approval_amount: int,
    account_address: str,
    contracts_to_check: list,
    execute_with_flash_loan: Callable
) -> Tuple[bool, int]:
    """Execute arbitrage opportunity."""
    try:
        # Validate token approvals
        needs_approval = not await token_checks.check_token_allowance(
            w3,
            opportunity['token_in'],
            token_abi,
            account_address,
            contracts_to_check,
            approval_amount
        )
        
        if needs_approval:
            logger.info("Approving tokens...")
            success = await approve_tokens(
                w3,
                opportunity['token_in'],
                token_abi,
                contracts_to_check,
                approval_amount,
                account_address
            )
            if not success:
                return False, 0
                
        # Execute flash loan transaction
        success = await execute_with_flash_loan(
            opportunity['token_in'],
            opportunity['amount'],
            opportunity['callback_data']
        )
        
        if not success:
            logger.error("Flash loan execution failed")
            return False, 0
            
        # Verify execution result
        profit = await verify_execution_result(
            w3,
            opportunity,
            account_address
        )
        
        return True, profit
        
    except Exception as e:
        logger.error(f"Error executing arbitrage: {e}")
        return False, 0

async def approve_tokens(
    w3: Web3,
    token: str,
    token_abi: list,
    spenders: list,
    amount: int,
    owner: str
) -> bool:
    """Approve token spending for multiple contracts."""
    try:
        token_contract = w3.eth.contract(
            address=token,
            abi=token_abi
        )
        
        for spender in spenders:
            try:
                # Check current allowance
                current_allowance = await token_contract.functions.allowance(
                    owner,
                    spender
                ).call()
                
                if current_allowance < amount:
                    # Build approval transaction
                    tx = await token_contract.functions.approve(
                        spender,
                        amount
                    ).build_transaction({
                        'from': owner,
                        'gas': 100000,
                        'maxFeePerGas': w3.eth.gas_price,
                        'nonce': await w3.eth.get_transaction_count(owner)
                    })
                    
                    # Send transaction
                    signed_tx = w3.eth.account.sign_transaction(tx, owner)
                    tx_hash = await w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                    
                    # Wait for confirmation
                    receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
                    if receipt['status'] != 1:
                        logger.error(f"Approval failed for spender {spender}")
                        return False
                        
            except Exception as e:
                logger.error(f"Error approving tokens for {spender}: {e}")
                return False
                
        return True
        
    except Exception as e:
        logger.error(f"Error in token approval process: {e}")
        return False

async def verify_execution_result(
    w3: Web3,
    opportunity: Dict,
    account: str
) -> int:
    """Verify arbitrage execution result and calculate actual profit."""
    try:
        # Get token contract
        token_contract = w3.eth.contract(
            address=opportunity['token_in'],
            abi=[{
                'inputs': [{'type': 'address', 'name': 'account'}],
                'name': 'balanceOf',
                'outputs': [{'type': 'uint256', 'name': ''}],
                'stateMutability': 'view',
                'type': 'function'
            }]
        )
        
        # Get final balance
        final_balance = await token_contract.functions.balanceOf(account).call()
        
        # Calculate actual profit
        profit = final_balance - opportunity['amount']
        
        # Validate profit meets expectations
        min_acceptable_profit = int(opportunity['profit'] * Decimal('0.9'))  # 90% of expected
        if profit < min_acceptable_profit:
            logger.warning(
                f"Profit lower than expected: {profit} < {min_acceptable_profit}"
            )
            
        return profit
        
    except Exception as e:
        logger.error(f"Error verifying execution result: {e}")
        return 0

async def monitor_transaction(
    w3: Web3,
    tx_hash: str,
    max_blocks: int = 2
) -> bool:
    """Monitor transaction inclusion and execution."""
    try:
        start_block = w3.eth.block_number
        
        while w3.eth.block_number <= start_block + max_blocks:
            try:
                receipt = await w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    if receipt['status'] == 1:
                        return True
                    else:
                        logger.error(f"Transaction failed: {tx_hash.hex()}")
                        return False
            except Exception:
                pass
                
            await asyncio.sleep(1)
            
        logger.error(f"Transaction not included within {max_blocks} blocks")
        return False
        
    except Exception as e:
        logger.error(f"Error monitoring transaction: {e}")
        return False
