// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@aave/core-v3/contracts/flashloan/base/FlashLoanSimpleReceiverBase.sol";
import "@aave/core-v3/contracts/interfaces/IPoolAddressesProvider.sol";

interface IUniswapV2Router {
    function swapExactTokensForTokens(
        uint amountIn,
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external returns (uint[] memory amounts);
}

contract FlashLoanReceiver is FlashLoanSimpleReceiverBase {
    address public owner;
    address public immutable uniswapRouter;
    address public immutable sushiswapRouter;

    constructor(
        address _addressProvider,
        address _uniswapRouter,
        address _sushiswapRouter
    ) FlashLoanSimpleReceiverBase(IPoolAddressesProvider(_addressProvider)) {
        owner = msg.sender;
        uniswapRouter = _uniswapRouter;
        sushiswapRouter = _sushiswapRouter;
    }

    struct ArbitrageParams {
        address tokenIn;
        address tokenOut;
        uint256 amountIn;
        uint256 minAmountOut;
        bool buyOnUniswap;
    }

    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external override returns (bool) {
        ArbitrageParams memory arbitrageParams = abi.decode(params, (ArbitrageParams));
        
        IERC20(arbitrageParams.tokenIn).approve(uniswapRouter, arbitrageParams.amountIn);
        IERC20(arbitrageParams.tokenIn).approve(sushiswapRouter, arbitrageParams.amountIn);

        address[] memory path = new address[](2);
        path[0] = arbitrageParams.tokenIn;
        path[1] = arbitrageParams.tokenOut;

        if (arbitrageParams.buyOnUniswap) {
            // Buy on Uniswap, sell on Sushiswap
            IUniswapV2Router(uniswapRouter).swapExactTokensForTokens(
                arbitrageParams.amountIn,
                arbitrageParams.minAmountOut,
                path,
                address(this),
                block.timestamp
            );

            uint256 receivedAmount = IERC20(arbitrageParams.tokenOut).balanceOf(address(this));
            path[0] = arbitrageParams.tokenOut;
            path[1] = arbitrageParams.tokenIn;

            IERC20(arbitrageParams.tokenOut).approve(sushiswapRouter, receivedAmount);
            IUniswapV2Router(sushiswapRouter).swapExactTokensForTokens(
                receivedAmount,
                arbitrageParams.amountIn,
                path,
                address(this),
                block.timestamp
            );
        } else {
            // Buy on Sushiswap, sell on Uniswap
            IUniswapV2Router(sushiswapRouter).swapExactTokensForTokens(
                arbitrageParams.amountIn,
                arbitrageParams.minAmountOut,
                path,
                address(this),
                block.timestamp
            );

            uint256 receivedAmount = IERC20(arbitrageParams.tokenOut).balanceOf(address(this));
            path[0] = arbitrageParams.tokenOut;
            path[1] = arbitrageParams.tokenIn;

            IERC20(arbitrageParams.tokenOut).approve(uniswapRouter, receivedAmount);
            IUniswapV2Router(uniswapRouter).swapExactTokensForTokens(
                receivedAmount,
                arbitrageParams.amountIn,
                path,
                address(this),
                block.timestamp
            );
        }

        uint256 amountToReturn = amount + premium;
        IERC20(asset).approve(address(POOL), amountToReturn);

        return true;
    }

    function approveToken(address token, address spender, uint256 amount) external {
        require(msg.sender == owner, "only owner");
        IERC20(token).approve(spender, amount);
    }

    function withdrawToken(address token, uint256 amount) external {
        require(msg.sender == owner, "only owner");
        IERC20(token).transfer(msg.sender, amount);
    }

    receive() external payable {}
}
