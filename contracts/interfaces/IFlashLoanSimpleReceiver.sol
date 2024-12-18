// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IFlashLoanSimpleReceiver {
    /**
     * @notice Executes an operation after receiving the flash-borrowed asset
     * @param asset The address of the flash-borrowed asset
     * @param amount The amount of the flash-borrowed asset
     * @param premium The fee of the flash-borrowed asset
     * @param initiator The address of the flashloan initiator
     * @param params The byte-encoded params passed when initiating the flashloan
     * @return True if the operation was successful, false otherwise
     */
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external returns (bool);

    /**
     * @notice Returns the address of the Pool that will receive the repayment of the flash loan
     * @return The address of the Pool
     */
    function POOL() external view returns (address);

    /**
     * @notice Returns the address of the Pool Addresses Provider
     * @return The address of the Pool Addresses Provider
     */
    function ADDRESSES_PROVIDER() external view returns (address);
}
