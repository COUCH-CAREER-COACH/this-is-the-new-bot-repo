// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "../interfaces/IPoolAddressesProvider.sol";

contract MockAddressesProvider is IPoolAddressesProvider {
    address private _pool;
    string private _marketId;
    mapping(bytes32 => address) private _addresses;
    address private _poolConfigurator;
    address private _priceOracle;
    address private _aclManager;
    address private _aclAdmin;
    address private _priceOracleSentinel;

    constructor(address pool) {
        _pool = pool;
        _marketId = "MOCK_MARKET";
    }

    function getMarketId() external view override returns (string memory) {
        return _marketId;
    }

    function setMarketId(string memory newMarketId) external override {
        _marketId = newMarketId;
    }

    function getAddress(bytes32 id) external view override returns (address) {
        return _addresses[id];
    }

    function setAddress(bytes32 id, address newAddress) external override {
        _addresses[id] = newAddress;
    }

    function setAddressAsProxy(bytes32 id, address implementationAddress) external override {
        _addresses[id] = implementationAddress;
    }

    function getPool() external view override returns (address) {
        return _pool;
    }

    function setPoolImpl(address pool) external {
        _pool = pool;
    }

    function getPoolConfigurator() external view override returns (address) {
        return _poolConfigurator;
    }

    function setPoolConfiguratorImpl(address configurator) external override {
        _poolConfigurator = configurator;
    }

    function getPriceOracle() external view override returns (address) {
        return _priceOracle;
    }

    function setPriceOracle(address priceOracle) external override {
        _priceOracle = priceOracle;
    }

    function getACLManager() external view override returns (address) {
        return _aclManager;
    }

    function setACLManager(address aclManager) external override {
        _aclManager = aclManager;
    }

    function getACLAdmin() external view override returns (address) {
        return _aclAdmin;
    }

    function setACLAdmin(address aclAdmin) external override {
        _aclAdmin = aclAdmin;
    }

    function getPriceOracleSentinel() external view override returns (address) {
        return _priceOracleSentinel;
    }

    function setPriceOracleSentinel(address oracleSentinel) external override {
        _priceOracleSentinel = oracleSentinel;
    }
}
