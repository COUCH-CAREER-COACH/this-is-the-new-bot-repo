// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract MockFlashLoanProvider {
    address public poolAddress;
    uint256 public constant FLASH_LOAN_FEE = 9; // 0.09%
    uint256 public constant FEE_DENOMINATOR = 10000;

    constructor() {
        poolAddress = address(this);
    }

    function getPool() external view returns (address) {
        return poolAddress;
    }

    function getMaxFlashLoan(address asset) external pure returns (uint256) {
        return type(uint256).max;
    }

    function flashLoan(
        address receiver,
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata modes,
        address onBehalfOf,
        bytes calldata params,
        uint16 referralCode
    ) external {
        // Mock flash loan execution
        // In a test environment, we just need to simulate the callback
        (bool success,) = receiver.call(
            abi.encodeWithSignature(
                "executeOperation(address[],uint256[],uint256[],address,bytes)",
                assets,
                amounts,
                calculateFees(amounts),
                msg.sender,
                params
            )
        );
        require(success, "Flash loan execution failed");
    }

    function calculateFees(uint256[] memory amounts) internal pure returns (uint256[] memory) {
        uint256[] memory fees = new uint256[](amounts.length);
        for (uint256 i = 0; i < amounts.length; i++) {
            fees[i] = (amounts[i] * FLASH_LOAN_FEE) / FEE_DENOMINATOR;
        }
        return fees;
    }
}
