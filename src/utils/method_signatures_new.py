"""Method signatures for common Ethereum contract functions."""

# Mapping of method signatures to their human-readable names and descriptions
METHOD_SIGNATURES = {
    # Uniswap V2 Router Methods
    "0x38ed1739": {
        "name": "swapExactTokensForTokens",
        "type": "DEX_SWAP",
        "dex": "Uniswap/Sushiswap",
        "description": "Swap exact amount of tokens for tokens"
    },
    "0x7ff36ab5": {
        "name": "swapExactETHForTokens",
        "type": "DEX_SWAP",
        "dex": "Uniswap/Sushiswap",
        "description": "Swap exact amount of ETH for tokens"
    },
    "0x18cbafe5": {
        "name": "swapExactTokensForETH",
        "type": "DEX_SWAP",
        "dex": "Uniswap/Sushiswap",
        "description": "Swap exact amount of tokens for ETH"
    },
    "0xfb3bdb41": {
        "name": "swapETHForExactTokens",
        "type": "DEX_SWAP",
        "dex": "Uniswap/Sushiswap",
        "description": "Swap ETH for exact amount of tokens"
    },
    "0x8803dbee": {
        "name": "swapTokensForExactTokens",
        "type": "DEX_SWAP",
        "dex": "Uniswap/Sushiswap",
        "description": "Swap tokens for exact amount of tokens"
    },
    
    # Uniswap V2 Pair Methods
    "0x022c0d9f": {
        "name": "swap",
        "type": "DEX_SWAP",
        "dex": "Uniswap/Sushiswap",
        "description": "Direct pair swap"
    },
    "0x0902f1ac": {
        "name": "getReserves",
        "type": "DEX_QUERY",
        "dex": "Uniswap/Sushiswap",
        "description": "Get pair reserves"
    },
    "0x5c11d795": {
        "name": "skim",
        "type": "DEX_LIQUIDITY",
        "dex": "Uniswap/Sushiswap",
        "description": "Skim tokens from pair"
    },
    "0xbc25cf77": {
        "name": "sync",
        "type": "DEX_LIQUIDITY",
        "dex": "Uniswap/Sushiswap",
        "description": "Sync pair reserves"
    },
    "0x6a627842": {
        "name": "mint",
        "type": "DEX_LIQUIDITY",
        "dex": "Uniswap/Sushiswap",
        "description": "Add liquidity to pair"
    },
    "0x89afcb44": {
        "name": "burn",
        "type": "DEX_LIQUIDITY",
        "dex": "Uniswap/Sushiswap",
        "description": "Remove liquidity from pair"
    },
    
    # Factory Methods
    "0xe6a43905": {
        "name": "createPair",
        "type": "DEX_FACTORY",
        "dex": "Uniswap/Sushiswap",
        "description": "Create new token pair"
    },
    "0xc9c65396": {
        "name": "createPair",
        "type": "DEX_FACTORY",
        "dex": "Uniswap/Sushiswap",
        "description": "Create new token pair (alternative)"
    },
    
    # ERC20 Token Methods
    "0xa9059cbb": {
        "name": "transfer",
        "type": "TOKEN",
        "protocol": "ERC20",
        "description": "Transfer tokens to address"
    },
    "0x095ea7b3": {
        "name": "approve",
        "type": "TOKEN",
        "protocol": "ERC20",
        "description": "Approve spender to use tokens"
    },
    "0x23b872dd": {
        "name": "transferFrom",
        "type": "TOKEN",
        "protocol": "ERC20",
        "description": "Transfer tokens from address to address"
    },
    
    # DEX Liquidity Methods
    "0xe8e33700": {
        "name": "addLiquidity",
        "type": "DEX_LIQUIDITY",
        "dex": "Uniswap/Sushiswap",
        "description": "Add liquidity to token pair"
    },
    "0xf305d719": {
        "name": "addLiquidityETH",
        "type": "DEX_LIQUIDITY",
        "dex": "Uniswap/Sushiswap",
        "description": "Add liquidity to ETH pair"
    },
    
    # NFT Methods
    "0x136021d9": {
        "name": "setApprovalForAll",
        "type": "NFT",
        "protocol": "ERC721",
        "description": "Set approval for all tokens"
    },
    "0x42842e0e": {
        "name": "safeTransferFrom",
        "type": "NFT",
        "protocol": "ERC721",
        "description": "Safely transfer NFT"
    }
}

def get_method_info(method_id: str) -> dict:
    """Get information about a method from its signature."""
    return METHOD_SIGNATURES.get(method_id, {
        "name": "Unknown",
        "type": "UNKNOWN",
        "description": "Unknown method"
    })

def is_dex_swap(method_id: str) -> bool:
    """Check if method is a DEX swap."""
    method = METHOD_SIGNATURES.get(method_id, {})
    return method.get('type') == 'DEX_SWAP'

def is_dex_related(method_id: str) -> bool:
    """Check if method is related to DEX operations."""
    method = METHOD_SIGNATURES.get(method_id, {})
    return method.get('type', '').startswith('DEX_')

def is_token_transfer(method_id: str) -> bool:
    """Check if method is a token transfer."""
    method = METHOD_SIGNATURES.get(method_id, {})
    return method.get('type') == 'TOKEN'

def is_liquidity_action(method_id: str) -> bool:
    """Check if method is a liquidity action."""
    method = METHOD_SIGNATURES.get(method_id, {})
    return method.get('type') == 'DEX_LIQUIDITY'
