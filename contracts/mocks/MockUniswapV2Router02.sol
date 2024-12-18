// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "../interfaces/IUniswapV2Router02.sol";

contract MockUniswapV2Router02 is IUniswapV2Router02 {
    address private immutable _factory;
    address private immutable _WETH;

    constructor(address factory_, address WETH_) {
        _factory = factory_;
        _WETH = WETH_;
    }

    function factory() external view returns (address) {
        return _factory;
    }

    function WETH() external view returns (address) {
        return _WETH;
    }

    // Mock exchange rates
    mapping(address => mapping(address => uint256)) private _exchangeRates;
    
    function setPrice(address tokenIn, address tokenOut, uint256 rate) external {
        _exchangeRates[tokenIn][tokenOut] = rate;
    }

    function getAmountsOut(uint256 amountIn, address[] memory path) external view returns (uint256[] memory amounts) {
        require(path.length >= 2, "Invalid path");
        amounts = new uint256[](path.length);
        amounts[0] = amountIn;
        
        for (uint256 i = 0; i < path.length - 1; i++) {
            uint256 rate = _exchangeRates[path[i]][path[i + 1]];
            require(rate > 0, "Rate not set");
            amounts[i + 1] = (amounts[i] * rate) / 1e18;
        }
    }

    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts) {
        require(path.length >= 2, "Invalid path");
        require(deadline >= block.timestamp, "Expired");
        
        // Calculate amounts
        amounts = new uint256[](path.length);
        amounts[0] = amountIn;
        
        for (uint256 i = 0; i < path.length - 1; i++) {
            uint256 rate = _exchangeRates[path[i]][path[i + 1]];
            require(rate > 0, "Rate not set");
            amounts[i + 1] = (amounts[i] * rate) / 1e18;
        }

        require(amounts[amounts.length - 1] >= amountOutMin, "Insufficient output amount");

        // Transfer tokens
        require(IERC20(path[0]).transferFrom(msg.sender, address(this), amountIn), "Transfer of input token failed");
        require(IERC20(path[path.length - 1]).transfer(to, amounts[amounts.length - 1]), "Transfer of output token failed");
        
        return amounts;
    }

    function getAddress() external view returns (address) {
        return address(this);
    }

    // Other required interface functions (not used in tests)
    function addLiquidity(
        address tokenA, address tokenB,
        uint amountADesired, uint amountBDesired,
        uint amountAMin, uint amountBMin,
        address to, uint deadline
    ) external pure returns (uint amountA, uint amountB, uint liquidity) {
        return (0, 0, 0);
    }
    function addLiquidityETH(
        address token, uint amountTokenDesired,
        uint amountTokenMin, uint amountETHMin,
        address to, uint deadline
    ) external payable returns (uint amountToken, uint amountETH, uint liquidity) {
        return (0, 0, 0);
    }
    function removeLiquidity(
        address tokenA, address tokenB,
        uint liquidity, uint amountAMin,
        uint amountBMin, address to,
        uint deadline
    ) external returns (uint amountA, uint amountB) {
        return (0, 0);
    }
    function removeLiquidityETH(
        address token, uint liquidity,
        uint amountTokenMin, uint amountETHMin,
        address to, uint deadline
    ) external returns (uint amountToken, uint amountETH) {
        return (0, 0);
    }
    function removeLiquidityWithPermit(
        address tokenA, address tokenB,
        uint liquidity, uint amountAMin,
        uint amountBMin, address to,
        uint deadline, bool approveMax,
        uint8 v, bytes32 r, bytes32 s
    ) external returns (uint amountA, uint amountB) {
        return (0, 0);
    }
    function removeLiquidityETHWithPermit(
        address token, uint liquidity,
        uint amountTokenMin, uint amountETHMin,
        address to, uint deadline,
        bool approveMax, uint8 v, bytes32 r, bytes32 s
    ) external returns (uint amountToken, uint amountETH) {
        return (0, 0);
    }
    function swapTokensForExactTokens(
        uint amountOut, uint amountInMax,
        address[] calldata path,
        address to, uint deadline
    ) external returns (uint[] memory amounts) {
        return new uint[](0);
    }
    function swapExactETHForTokens(
        uint amountOutMin, address[] calldata path,
        address to, uint deadline
    ) external payable returns (uint[] memory amounts) {
        return new uint[](0);
    }
    function swapTokensForExactETH(
        uint amountOut, uint amountInMax,
        address[] calldata path,
        address to, uint deadline
    ) external returns (uint[] memory amounts) {
        return new uint[](0);
    }
    function swapExactTokensForETH(
        uint amountIn, uint amountOutMin,
        address[] calldata path,
        address to, uint deadline
    ) external returns (uint[] memory amounts) {
        return new uint[](0);
    }
    function swapETHForExactTokens(
        uint amountOut, address[] calldata path,
        address to, uint deadline
    ) external payable returns (uint[] memory amounts) {
        return new uint[](0);
    }
    function quote(
        uint amountA, uint reserveA,
        uint reserveB
    ) external pure returns (uint amountB) {
        return 0;
    }
    function getAmountOut(
        uint amountIn, uint reserveIn,
        uint reserveOut
    ) external pure returns (uint amountOut) {
        return 0;
    }
    function getAmountIn(
        uint amountOut, uint reserveIn,
        uint reserveOut
    ) external pure returns (uint amountIn) {
        return 0;
    }
    function getAmountsIn(
        uint amountOut,
        address[] calldata path
    ) external pure returns (uint[] memory amounts) {
        return new uint[](0);
    }
}
