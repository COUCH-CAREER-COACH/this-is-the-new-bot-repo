"""ABI handling utilities."""
from typing import Dict, List, Any, Optional
import json
from pathlib import Path

from ..logger_config import logger
from ..exceptions import ContractError

def load_abi(path: str) -> List[Dict[str, Any]]:
    """Load ABI from JSON file."""
    try:
        with open(path, 'r') as f:
            abi = json.load(f)
        if not isinstance(abi, list):
            raise ContractError(f"Invalid ABI format in {path}")
        return abi
    except Exception as e:
        logger.error(f"Error loading ABI from {path}: {e}")
        raise ContractError(f"Failed to load ABI: {e}")

def get_function_selector(
    function_name: str,
    parameter_types: List[str]
) -> str:
    """Get function selector (first 4 bytes of keccak hash)."""
    try:
        from eth_abi.packed import encode_packed
        from eth_utils import keccak
        
        # Create function signature
        signature = f"{function_name}({','.join(parameter_types)})"
        
        # Get selector
        selector = keccak(encode_packed(['string'], [signature]))[:4].hex()
        
        return f"0x{selector}"
        
    except Exception as e:
        logger.error(f"Error getting function selector: {e}")
        raise ContractError(f"Failed to get function selector: {e}")

def encode_function_data(
    abi: List[Dict[str, Any]],
    function_name: str,
    args: List[Any]
) -> str:
    """Encode function call data."""
    try:
        from eth_abi import encode
        
        # Find function in ABI
        function = None
        for item in abi:
            if item.get('type') == 'function' and item.get('name') == function_name:
                function = item
                break
                
        if not function:
            raise ContractError(f"Function {function_name} not found in ABI")
            
        # Get parameter types
        parameter_types = [input_['type'] for input_ in function['inputs']]
        
        # Get function selector
        selector = get_function_selector(function_name, parameter_types)
        
        # Encode parameters
        encoded_params = encode(parameter_types, args).hex()
        
        return f"{selector}{encoded_params}"
        
    except Exception as e:
        logger.error(f"Error encoding function data: {e}")
        raise ContractError(f"Failed to encode function data: {e}")

def decode_function_data(
    abi: List[Dict[str, Any]],
    data: str
) -> Optional[Dict[str, Any]]:
    """Decode function call data."""
    try:
        from eth_abi import decode
        
        if not data.startswith('0x'):
            data = f"0x{data}"
            
        # Get function selector
        selector = data[:10]
        
        # Find matching function in ABI
        function = None
        for item in abi:
            if item.get('type') == 'function':
                item_selector = get_function_selector(
                    item['name'],
                    [input_['type'] for input_ in item['inputs']]
                )
                if item_selector == selector:
                    function = item
                    break
                    
        if not function:
            return None
            
        # Decode parameters
        parameter_types = [input_['type'] for input_ in function['inputs']]
        parameter_names = [input_['name'] for input_ in function['inputs']]
        
        decoded_params = decode(
            parameter_types,
            bytes.fromhex(data[10:])
        )
        
        return {
            'function': function['name'],
            'params': dict(zip(parameter_names, decoded_params))
        }
        
    except Exception as e:
        logger.error(f"Error decoding function data: {e}")
        return None

def get_event_topic(
    event_name: str,
    parameter_types: List[str]
) -> str:
    """Get event topic (keccak hash of event signature)."""
    try:
        from eth_abi.packed import encode_packed
        from eth_utils import keccak
        
        # Create event signature
        signature = f"{event_name}({','.join(parameter_types)})"
        
        # Get topic
        topic = keccak(encode_packed(['string'], [signature])).hex()
        
        return f"0x{topic}"
        
    except Exception as e:
        logger.error(f"Error getting event topic: {e}")
        raise ContractError(f"Failed to get event topic: {e}")

def decode_event_data(
    abi: List[Dict[str, Any]],
    topics: List[str],
    data: str
) -> Optional[Dict[str, Any]]:
    """Decode event log data."""
    try:
        from eth_abi import decode
        
        if not data.startswith('0x'):
            data = f"0x{data}"
            
        # Find matching event in ABI
        event = None
        for item in abi:
            if item.get('type') == 'event':
                event_topic = get_event_topic(
                    item['name'],
                    [input_['type'] for input_ in item['inputs']]
                )
                if event_topic == topics[0]:
                    event = item
                    break
                    
        if not event:
            return None
            
        # Separate indexed and non-indexed parameters
        indexed_types = []
        indexed_names = []
        non_indexed_types = []
        non_indexed_names = []
        
        for input_ in event['inputs']:
            if input_['indexed']:
                indexed_types.append(input_['type'])
                indexed_names.append(input_['name'])
            else:
                non_indexed_types.append(input_['type'])
                non_indexed_names.append(input_['name'])
                
        # Decode parameters
        indexed_values = []
        for topic in topics[1:]:  # Skip first topic (event signature)
            decoded = decode(['bytes32'], [bytes.fromhex(topic[2:])])[0]
            indexed_values.append(decoded)
            
        non_indexed_values = decode(
            non_indexed_types,
            bytes.fromhex(data[2:])
        ) if non_indexed_types else []
        
        # Combine parameters
        params = {}
        for name, value in zip(indexed_names, indexed_values):
            params[name] = value
        for name, value in zip(non_indexed_names, non_indexed_values):
            params[name] = value
            
        return {
            'event': event['name'],
            'params': params
        }
        
    except Exception as e:
        logger.error(f"Error decoding event data: {e}")
        return None

def validate_abi(abi: List[Dict[str, Any]]) -> bool:
    """Validate ABI format and content."""
    try:
        if not isinstance(abi, list):
            return False
            
        required_fields = {
            'function': ['name', 'inputs', 'outputs'],
            'event': ['name', 'inputs'],
            'constructor': ['inputs'],
            'fallback': []
        }
        
        for item in abi:
            # Check item is a dictionary
            if not isinstance(item, dict):
                return False
                
            # Check item has type field
            if 'type' not in item:
                return False
                
            # Check type is valid
            item_type = item['type']
            if item_type not in required_fields:
                return False
                
            # Check required fields for type
            for field in required_fields[item_type]:
                if field not in item:
                    return False
                    
            # Validate inputs and outputs if present
            for io_list in ['inputs', 'outputs']:
                if io_list in item:
                    if not isinstance(item[io_list], list):
                        return False
                    for io in item[io_list]:
                        if not isinstance(io, dict):
                            return False
                        if 'type' not in io:
                            return False
                            
        return True
        
    except Exception as e:
        logger.error(f"Error validating ABI: {e}")
        return False

def merge_abis(*abis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge multiple ABIs, removing duplicates."""
    try:
        merged = []
        seen = set()
        
        for abi in abis:
            for item in abi:
                # Create unique key for item
                if item['type'] == 'function':
                    key = f"function:{item['name']}({','.join(i['type'] for i in item['inputs'])})"
                elif item['type'] == 'event':
                    key = f"event:{item['name']}({','.join(i['type'] for i in item['inputs'])})"
                else:
                    key = f"{item['type']}"
                    
                if key not in seen:
                    seen.add(key)
                    merged.append(item)
                    
        return merged
        
    except Exception as e:
        logger.error(f"Error merging ABIs: {e}")
        raise ContractError(f"Failed to merge ABIs: {e}")

def save_abi(abi: List[Dict[str, Any]], path: str) -> None:
    """Save ABI to JSON file."""
    try:
        # Validate ABI first
        if not validate_abi(abi):
            raise ContractError("Invalid ABI format")
            
        # Create directory if it doesn't exist
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save ABI
        with open(path, 'w') as f:
            json.dump(abi, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error saving ABI to {path}: {e}")
        raise ContractError(f"Failed to save ABI: {e}")
