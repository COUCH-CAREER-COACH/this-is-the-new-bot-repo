// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "../interfaces/IPoolAddressesProvider.sol";

contract MockPoolAddressesProvider is IPoolAddressesProvider {
    address private _pool;
    address private _priceOracle;
    address private _aclAdmin;
    address private _aclManager;
    address private _poolConfigurator;
    address private _priceOracleSentinel;

    string private _marketId;

    function getPool() external view override returns (address) {
        return _pool;
    }

    function setPoolImpl(address pool) external override {
        _pool = pool;
    }

    function getMarketId() external view override returns (string memory) {
        return _marketId;
    }

    function setMarketId(string memory newMarketId) external override {
        _marketId = newMarketId;
    }

    function getAddress(bytes32 id) external view override returns (address) {
        return address(0);
    }

    function setAddressAsProxy(bytes32 id, address implementationAddress) external override {}
    
    function setAddress(bytes32 id, address newAddress) external override {}

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
