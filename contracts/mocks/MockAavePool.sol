// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "../interfaces/IPool.sol";
import "../interfaces/IPoolAddressesProvider.sol";
import "../interfaces/DataTypes.sol";
import "hardhat/console.sol";

interface IFlashLoanSimpleReceiver {
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external returns (bool);
}

contract MockAavePool is IPool {
    IPoolAddressesProvider private immutable _addressesProvider;
    mapping(address => mapping(address => bool)) private _approvals;

    event FlashLoan(
        address indexed receiver,
        address indexed asset,
        uint256 amount,
        uint256 premium
    );

    event Approval(address indexed token, address indexed spender, bool approved);

    constructor(address provider) {
        _addressesProvider = IPoolAddressesProvider(provider);
    }

    function setApproval(address token, address spender, bool approved) external {
        _approvals[token][spender] = approved;
        // Also approve the ERC20 token
        if (approved) {
            require(
                IERC20(token).approve(spender, type(uint256).max),
                "ERC20 approval failed"
            );
            emit Approval(token, spender, true);
            console.log("Approved token:", token);
            console.log("Approved spender:", spender);
            console.log("Approval status:", approved);
        } else {
            require(
                IERC20(token).approve(spender, 0),
                "ERC20 approval revocation failed"
            );
            emit Approval(token, spender, false);
            console.log("Revoked approval for token:", token);
            console.log("Revoked spender:", spender);
        }
    }

    function isApproved(address token, address spender) public view returns (bool) {
        return _approvals[token][spender] && IERC20(token).allowance(address(this), spender) > 0;
    }

    function flashLoanSimple(
        address receiverAddress,
        address asset,
        uint256 amount,
        bytes calldata params,
        uint16 referralCode
    ) external override {
        require(isApproved(asset, receiverAddress), "MockAavePool: receiver not approved");
        
        uint256 balance = IERC20(asset).balanceOf(address(this));
        require(balance >= amount, "Insufficient balance");
        
        // Transfer tokens to receiver
        require(
            IERC20(asset).transfer(receiverAddress, amount),
            string(
                abi.encodePacked(
                    "Transfer to receiver failed. Balance: ",
                    balance,
                    ", Amount: ",
                    amount
                )
            )
        );

        emit FlashLoan(receiverAddress, asset, amount, 0);

        // Call executeOperation on receiver
        require(
            IFlashLoanSimpleReceiver(receiverAddress).executeOperation(
                asset,
                amount,
                0, // No premium in mock
                msg.sender,
                params
            ),
            "Flash loan execution failed"
        );

        // Get tokens back from receiver
        require(
            IERC20(asset).transferFrom(receiverAddress, address(this), amount),
            "Repayment failed"
        );
    }

    // Required interface implementations
    function ADDRESSES_PROVIDER() external view override returns (IPoolAddressesProvider) {
        return _addressesProvider;
    }

    function supply(address asset, uint256 amount, address onBehalfOf, uint16 referralCode) external override {}
    function withdraw(address asset, uint256 amount, address to) external override returns (uint256) { return 0; }
    function borrow(address asset, uint256 amount, uint256 interestRateMode, uint16 referralCode, address onBehalfOf) external override {}
    function repay(address asset, uint256 amount, uint256 interestRateMode, address onBehalfOf) external override returns (uint256) { return 0; }
    function setUserUseReserveAsCollateral(address asset, bool useAsCollateral) external override {}
    function liquidationCall(address collateralAsset, address debtAsset, address user, uint256 debtToCover, bool receiveAToken) external override {}
    function getReserveData(address asset) external view override returns (DataTypes.ReserveData memory) {}
    function getUserAccountData(address user) external view override returns (uint256 totalCollateralETH, uint256 totalDebtETH, uint256 availableBorrowsETH, uint256 currentLiquidationThreshold, uint256 ltv, uint256 healthFactor) { return (0,0,0,0,0,0); }
}
