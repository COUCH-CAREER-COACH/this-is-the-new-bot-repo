// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IPoolAddressesProvider.sol";
import "./interfaces/IPool.sol";
import "./interfaces/IUniswapV2Router02.sol";
import "./interfaces/IFlashLoanSimpleReceiver.sol";

// Custom errors for gas optimization
error InvalidAmount(uint256 amount, string reason);
error InvalidAddress(address addr, string reason);
error InvalidConfiguration(string reason);
error UnauthorizedCaller(address caller, address expected);
error InsufficientProfit(uint256 actual, uint256 expected);
error ExcessiveSlippage(uint256 expected, uint256 actual);
error TransactionTimeout();
error PriceDeviation(uint256 expected, uint256 actual);

contract FlashLoanArbitrage is IFlashLoanSimpleReceiver, Ownable, ReentrancyGuard, Pausable {
    using Math for uint256;

    // Immutable state variables
    address public immutable WETH;
    IPoolAddressesProvider public immutable provider;
    IPool public immutable lendingPool;
    IUniswapV2Router02 public immutable uniswapRouter;
    
    // Storage variables - packed for gas optimization
    address public intermediateToken;
    uint32 public maxPriceDeviation; // Max allowed price deviation in basis points (e.g., 500 = 5%)
    uint32 public maxSlippage; // Max allowed slippage in basis points
    uint32 public minProfitBps; // Minimum profit in basis points
    uint32 public constant MAX_BPS = 10000;
    uint256 public maxFlashLoanAmount;
    uint256 public lastExecutionTime;
    uint256 public constant MIN_EXECUTION_DELAY = 2; // Minimum delay between executions in blocks
    
    // Monitoring variables
    uint256 public totalProfitGenerated;
    uint256 public totalGasUsed;
    uint256 public successfulTrades;
    uint256 public failedTrades;
    
    mapping(address => bool) private hasApprovedToken;
    mapping(address => uint256) public lastKnownPrice;
    
    // Enhanced events for better monitoring
    event FlashLoanInitiated(
        address indexed asset,
        uint256 amount,
        uint256 gasPrice,
        uint256 estimatedProfit
    );
    event ArbitrageExecuted(
        address indexed asset,
        address indexed intermediateToken,
        uint256 flashLoanAmount,
        uint256 profit,
        uint256 gasUsed,
        uint256 effectiveGasPrice
    );
    event ProfitWithdrawn(
        address indexed token,
        uint256 amount,
        uint256 totalProfitToDate
    );
    event TokenApproved(address indexed token, address indexed spender);
    event MaxFlashLoanAmountUpdated(uint256 newAmount);
    event MinProfitBpsUpdated(uint256 newBps);
    event PriceDeviationDetected(
        address indexed token,
        uint256 expectedPrice,
        uint256 actualPrice,
        uint256 deviationBps
    );
    event EmergencyWithdraw(
        address indexed token,
        address indexed to,
        uint256 amount,
        string reason
    );
    event TradeMetrics(
        uint256 slippage,
        uint256 priceImpact,
        uint256 gasUsed,
        bool profitable
    );

    constructor(
        address _poolAddressesProvider,
        address _uniswapRouter,
        address _weth,
        uint256 _maxFlashLoanAmount,
        uint32 _minProfitBps
    ) {
        if (_maxFlashLoanAmount == 0) revert InvalidAmount(_maxFlashLoanAmount, "Max flash loan amount cannot be 0");
        if (_minProfitBps == 0 || _minProfitBps >= MAX_BPS) revert InvalidAmount(_minProfitBps, "Invalid min profit bps");
        if (_poolAddressesProvider == address(0)) revert InvalidAddress(_poolAddressesProvider, "Invalid pool provider");
        if (_uniswapRouter == address(0)) revert InvalidAddress(_uniswapRouter, "Invalid router");
        if (_weth == address(0)) revert InvalidAddress(_weth, "Invalid WETH");
        
        provider = IPoolAddressesProvider(_poolAddressesProvider);
        lendingPool = IPool(provider.getPool());
        uniswapRouter = IUniswapV2Router02(_uniswapRouter);
        WETH = _weth;
        maxFlashLoanAmount = _maxFlashLoanAmount;
        minProfitBps = _minProfitBps;
        maxPriceDeviation = 500; // 5% default
        maxSlippage = 100; // 1% default
    }

    // Configuration functions
    function setMaxFlashLoanAmount(uint256 newAmount) external onlyOwner {
        if (newAmount == 0) revert InvalidAmount(newAmount, "Amount cannot be 0");
        maxFlashLoanAmount = newAmount;
        emit MaxFlashLoanAmountUpdated(newAmount);
    }

    function setMinProfitBps(uint32 newBps) external onlyOwner {
        if (newBps == 0 || newBps >= MAX_BPS) revert InvalidAmount(newBps, "Invalid bps");
        minProfitBps = newBps;
        emit MinProfitBpsUpdated(newBps);
    }

    function setMaxPriceDeviation(uint32 newDeviation) external onlyOwner {
        if (newDeviation == 0 || newDeviation >= MAX_BPS) revert InvalidAmount(newDeviation, "Invalid deviation");
        maxPriceDeviation = newDeviation;
    }

    function setMaxSlippage(uint32 newSlippage) external onlyOwner {
        if (newSlippage == 0 || newSlippage >= MAX_BPS) revert InvalidAmount(newSlippage, "Invalid slippage");
        maxSlippage = newSlippage;
    }

    function setIntermediateToken(address token) external onlyOwner {
        if (token == address(0)) revert InvalidAddress(token, "Invalid token address");
        intermediateToken = token;
    }

    // Main flash loan function
    function initiateFlashLoan(
        address asset,
        uint256 amount
    ) external nonReentrant whenNotPaused {
        // Basic validation
        if (intermediateToken == address(0)) revert InvalidAddress(intermediateToken, "Intermediate token not set");
        if (amount == 0) revert InvalidAmount(amount, "Amount must be greater than 0");
        if (amount > maxFlashLoanAmount) revert InvalidAmount(amount, "Amount exceeds maximum");
        
        // Prevent sandwich attacks by checking block delay
        if (block.number - lastExecutionTime < MIN_EXECUTION_DELAY) revert("Too soon");
        lastExecutionTime = block.number;

        // Verify configuration
        if (address(lendingPool) != this.POOL()) revert InvalidConfiguration("Invalid pool");
        if (address(provider) != this.ADDRESSES_PROVIDER()) revert InvalidConfiguration("Invalid provider");

        // Check price deviation
        uint256[] memory amountsOut = _checkPriceDeviation(asset, amount);
        
        // Calculate estimated profit
        uint256 estimatedProfit = _calculateEstimatedProfit(asset, amount, amountsOut);
        
        // Set up flash loan
        _setupFlashLoan(asset, amount);
        
        // Emit detailed event
        emit FlashLoanInitiated(
            asset,
            amount,
            tx.gasprice,
            estimatedProfit
        );

        // Execute flash loan
        bytes memory params = "";
        lendingPool.flashLoanSimple(
            address(this),
            asset,
            amount,
            params,
            0
        );
    }

    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external override returns (bool) {
        if (msg.sender != address(lendingPool)) revert UnauthorizedCaller(msg.sender, address(lendingPool));
        if (initiator != address(this)) revert UnauthorizedCaller(initiator, address(this));
        
        uint256 startGas = gasleft();
        bool success;
        
        try this._executeArbitrage(asset, amount, amount + premium) returns (bool _success) {
            success = _success;
        } catch (bytes memory reason) {
            failedTrades++;
            emit TradeMetrics(0, 0, startGas - gasleft(), false);
            revert(string(reason));
        }

        if (success) {
            successfulTrades++;
            uint256 gasUsed = startGas - gasleft();
            totalGasUsed += gasUsed;
            
            emit TradeMetrics(
                _calculateSlippage(amount, IERC20(asset).balanceOf(address(this))),
                _calculatePriceImpact(asset, amount),
                gasUsed,
                true
            );
        }

        return success;
    }

    // Interface implementations
    function ADDRESSES_PROVIDER() external view returns (address) {
        return address(provider);
    }

    function POOL() external view returns (address) {
        return address(lendingPool);
    }

    // Internal functions
    function _executeArbitrage(
        address asset,
        uint256 amount,
        uint256 amountOwed
    ) external returns (bool) {
        if (msg.sender != address(this)) revert UnauthorizedCaller(msg.sender, address(this));
        
        // First trade
        uint256 intermediateAmount = _executeFirstTrade(asset, amount);
        
        // Second trade
        uint256 finalAmount = _executeSecondTrade(asset, intermediateAmount, amountOwed);
        
        // Verify profit
        uint256 profit = finalAmount - amountOwed;
        if (profit * MAX_BPS < amountOwed * minProfitBps) {
            revert InsufficientProfit(profit, amountOwed * minProfitBps / MAX_BPS);
        }

        // Update total profit
        unchecked {
            totalProfitGenerated += profit;
        }

        emit ArbitrageExecuted(
            asset,
            intermediateToken,
            amount,
            profit,
            gasleft(),
            tx.gasprice
        );

        return true;
    }

    function _executeFirstTrade(
        address asset,
        uint256 amount
    ) internal returns (uint256) {
        address[] memory path = new address[](2);
        path[0] = asset;
        path[1] = intermediateToken;

        uint256[] memory amountsOut = uniswapRouter.getAmountsOut(amount, path);
        uint256 minAmountOut = _calculateMinAmountOut(amountsOut[1]);

        uint256[] memory received = uniswapRouter.swapExactTokensForTokens(
            amount,
            minAmountOut,
            path,
            address(this),
            block.timestamp + 300
        );

        if (received[1] < minAmountOut) {
            revert ExcessiveSlippage(minAmountOut, received[1]);
        }

        return received[1];
    }

    function _executeSecondTrade(
        address asset,
        uint256 amount,
        uint256 minimumReturn
    ) internal returns (uint256) {
        address[] memory path = new address[](2);
        path[0] = intermediateToken;
        path[1] = asset;

        uint256[] memory amountsOut = uniswapRouter.getAmountsOut(amount, path);
        uint256 minAmountOut = _calculateMinAmountOut(amountsOut[1]);

        if (minAmountOut < minimumReturn) {
            revert InsufficientProfit(minAmountOut, minimumReturn);
        }

        uint256[] memory received = uniswapRouter.swapExactTokensForTokens(
            amount,
            minAmountOut,
            path,
            address(this),
            block.timestamp + 300
        );

        return received[1];
    }

    // Utility functions
    function _calculateMinAmountOut(uint256 amount) internal view returns (uint256) {
        return amount - ((amount * maxSlippage) / MAX_BPS);
    }

    function _calculateSlippage(uint256 expected, uint256 actual) internal pure returns (uint256) {
        if (actual >= expected) return 0;
        return ((expected - actual) * MAX_BPS) / expected;
    }

    function _calculatePriceImpact(address token, uint256 amount) internal view returns (uint256) {
        if (lastKnownPrice[token] == 0) return 0;
        uint256 currentPrice = _getCurrentPrice(token);
        return _calculateSlippage(lastKnownPrice[token], currentPrice);
    }

    function _getCurrentPrice(address token) internal view returns (uint256) {
        address[] memory path = new address[](2);
        path[0] = token;
        path[1] = WETH;
        uint256[] memory amounts = uniswapRouter.getAmountsOut(1e18, path);
        return amounts[1];
    }

    function _checkPriceDeviation(address asset, uint256 amount) internal returns (uint256[] memory) {
        address[] memory path = new address[](2);
        path[0] = asset;
        path[1] = WETH;
        
        uint256[] memory amountsOut = uniswapRouter.getAmountsOut(1e18, path);
        uint256 currentPrice = amountsOut[1];
        
        if (lastKnownPrice[asset] != 0) {
            uint256 deviation = _calculateSlippage(lastKnownPrice[asset], currentPrice);
            if (deviation > maxPriceDeviation) {
                emit PriceDeviationDetected(asset, lastKnownPrice[asset], currentPrice, deviation);
                revert PriceDeviation(lastKnownPrice[asset], currentPrice);
            }
        }
        
        lastKnownPrice[asset] = currentPrice;
        return amountsOut;
    }

    function _calculateEstimatedProfit(
        address asset,
        uint256 amount,
        uint256[] memory amountsOut
    ) internal view returns (uint256) {
        address[] memory path = new address[](2);
        path[0] = asset;
        path[1] = intermediateToken;
        
        uint256[] memory firstTrade = uniswapRouter.getAmountsOut(amount, path);
        
        path[0] = intermediateToken;
        path[1] = asset;
        
        uint256[] memory secondTrade = uniswapRouter.getAmountsOut(firstTrade[1], path);
        
        return secondTrade[1] > amount ? secondTrade[1] - amount : 0;
    }

    function _setupFlashLoan(address asset, uint256 amount) internal {
        // Reset and set approvals with unchecked for gas optimization
        unchecked {
            IERC20(asset).approve(address(lendingPool), 0);
            IERC20(asset).approve(address(lendingPool), amount * 2); // Approve for amount plus potential premium
        }
    }

    // Emergency functions
    function emergencyWithdraw(
        address token,
        address to,
        string calldata reason
    ) external onlyOwner nonReentrant {
        if (token == address(0)) revert InvalidAddress(token, "Invalid token");
        if (to == address(0)) revert InvalidAddress(to, "Invalid recipient");
        
        uint256 balance = IERC20(token).balanceOf(address(this));
        if (balance == 0) revert InvalidAmount(balance, "No tokens to withdraw");
        
        IERC20(token).transfer(to, balance);
        emit EmergencyWithdraw(token, to, balance, reason);
    }

    // View functions for monitoring
    function getTradeStatistics() external view returns (
        uint256 totalProfit,
        uint256 avgGasUsed,
        uint256 successRate,
        uint256 totalTrades
    ) {
        totalProfit = totalProfitGenerated;
        totalTrades = successfulTrades + failedTrades;
        avgGasUsed = totalTrades > 0 ? totalGasUsed / totalTrades : 0;
        successRate = totalTrades > 0 ? (successfulTrades * MAX_BPS) / totalTrades : 0;
    }

    receive() external payable {}
}
