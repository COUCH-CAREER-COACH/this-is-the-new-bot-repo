// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IPoolAddressesProvider {
    function getPool() external view returns (address);
    function setPoolImpl(address pool) external;
    function getMarketId() external view returns (string memory);
    function setMarketId(string memory newMarketId) external;
    function getAddress(bytes32 id) external view returns (address);
    function setAddressAsProxy(bytes32 id, address implementationAddress) external;
    function setAddress(bytes32 id, address newAddress) external;
    function getPoolConfigurator() external view returns (address);
    function setPoolConfiguratorImpl(address configurator) external;
    function getPriceOracle() external view returns (address);
    function setPriceOracle(address priceOracle) external;
    function getACLManager() external view returns (address);
    function setACLManager(address aclManager) external;
    function getACLAdmin() external view returns (address);
    function setACLAdmin(address aclAdmin) external;
    function getPriceOracleSentinel() external view returns (address);
    function setPriceOracleSentinel(address oracleSentinel) external;
}
