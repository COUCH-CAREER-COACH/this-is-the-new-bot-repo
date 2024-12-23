"""Custom exceptions for the arbitrage bot."""

class ArbitrageError(Exception):
    """Base exception for arbitrage bot errors."""
    pass

class ConnectionError(ArbitrageError):
    """Raised when connection issues occur."""
    pass

class TransactionError(ArbitrageError):
    """Raised when transaction execution fails."""
    pass

class LatencyError(ArbitrageError):
    """Raised when latency exceeds acceptable limits."""
    pass

class NetworkError(ArbitrageError):
    """Raised when network-related issues occur."""
    pass

class ConfigurationError(ArbitrageError):
    """Raised when there is an error in configuration."""
    pass

class ValidationError(ArbitrageError):
    """Raised when validation fails."""
    pass

class SecurityError(ArbitrageError):
    """Raised when security checks fail."""
    pass

class TokenError(ArbitrageError):
    """Raised when there are token-related issues."""
    pass

class GasError(ArbitrageError):
    """Raised when there are gas-related issues."""
    pass

class CalculationError(ArbitrageError):
    """Raised when calculation fails."""
    pass

class ExecutionError(ArbitrageError):
    """Raised when execution fails."""
    pass

class InsufficientLiquidityError(ArbitrageError):
    """Raised when there is insufficient liquidity."""
    pass

class ExcessiveSlippageError(ArbitrageError):
    """Raised when slippage exceeds maximum."""
    pass

class GasEstimationError(ArbitrageError):
    """Raised when gas estimation fails."""
    pass

class ContractError(ArbitrageError):
    """Raised when there are contract-related issues."""
    pass

class RiskLimitExceeded(ArbitrageError):
    """Raised when risk limits are exceeded."""
    pass

class CircuitBreakerTriggered(ArbitrageError):
    """Raised when circuit breaker is triggered."""
    pass

class ExposureLimitExceeded(ArbitrageError):
    """Raised when exposure limits are exceeded."""
    pass

class SlippageExceeded(ArbitrageError):
    """Raised when slippage exceeds limits."""
    pass

class MEVCompetitionError(ArbitrageError):
    """Raised when MEV competition is too high."""
    pass

class PositionSizeError(ArbitrageError):
    """Raised when position size is invalid."""
    pass

class OptimizationError(ArbitrageError):
    """Raised when optimization fails."""
    pass

class MonitoringError(ArbitrageError):
    """Raised when monitoring fails."""
    pass

class FlashLoanError(ArbitrageError):
    """Raised when flash loan operation fails."""
    pass

class DEXError(ArbitrageError):
    """Raised when DEX interaction fails."""
    pass

class BlockchainError(ArbitrageError):
    """Raised when blockchain interaction fails."""
    pass

class StrategyError(ArbitrageError):
    """Raised when strategy execution fails."""
    pass

class DataError(ArbitrageError):
    """Raised when data handling fails."""
    pass

class CacheError(ArbitrageError):
    """Raised when cache operations fail."""
    pass

class TimeoutError(ArbitrageError):
    """Raised when operation times out."""
    pass

class MemoryError(ArbitrageError):
    """Raised when memory limits are exceeded."""
    pass

class ResourceError(ArbitrageError):
    """Raised when system resources are exhausted."""
    pass

class MainnetError(ArbitrageError):
    """Raised when mainnet-specific operations fail."""
    pass

class SimulationError(ArbitrageError):
    """Raised when transaction simulation fails."""
    pass

class FlashbotsError(ArbitrageError):
    """Raised when Flashbots interaction fails."""
    pass

class MetricsError(ArbitrageError):
    """Raised when metrics collection fails."""
    pass

class AlertError(ArbitrageError):
    """Raised when alert system fails."""
    pass

class RecoveryError(ArbitrageError):
    """Raised when recovery operation fails."""
    pass

class UpgradeError(ArbitrageError):
    """Raised when upgrade process fails."""
    pass

class VersionError(ArbitrageError):
    """Raised when version compatibility fails."""
    pass

class StateError(ArbitrageError):
    """Raised when state management fails."""
    pass

class BackupError(ArbitrageError):
    """Raised when backup operation fails."""
    pass

class RestoreError(ArbitrageError):
    """Raised when restore operation fails."""
    pass

class MaintenanceError(ArbitrageError):
    """Raised when maintenance operation fails."""
    pass

class DeploymentError(ArbitrageError):
    """Raised when deployment fails."""
    pass

class VerificationError(ArbitrageError):
    """Raised when verification fails."""
    pass

class ComplianceError(ArbitrageError):
    """Raised when compliance check fails."""
    pass

class AuditError(ArbitrageError):
    """Raised when audit check fails."""
    pass

class PermissionError(ArbitrageError):
    """Raised when permission check fails."""
    pass

class AuthenticationError(ArbitrageError):
    """Raised when authentication fails."""
    pass

class AuthorizationError(ArbitrageError):
    """Raised when authorization fails."""
    pass

class AccessError(ArbitrageError):
    """Raised when access is denied."""
    pass

class EnvironmentError(ArbitrageError):
    """Raised when environment setup fails."""
    pass

class DependencyError(ArbitrageError):
    """Raised when dependency check fails."""
    pass

class IntegrationError(ArbitrageError):
    """Raised when integration fails."""
    pass

class ServiceError(ArbitrageError):
    """Raised when service operation fails."""
    pass

class HealthCheckError(ArbitrageError):
    """Raised when health check fails."""
    pass

class WebSocketError(ArbitrageError):
    """Raised when WebSocket operations fail."""
    pass

class RPCError(ArbitrageError):
    """Raised when RPC operations fail."""
    pass

class ProviderError(ArbitrageError):
    """Raised when provider operations fail."""
    pass

class SignatureError(ArbitrageError):
    """Raised when signature operations fail."""
    pass

class NonceError(ArbitrageError):
    """Raised when nonce management fails."""
    pass

class RevertError(ArbitrageError):
    """Raised when transaction reverts."""
    pass

class BalanceError(ArbitrageError):
    """Raised when balance is insufficient."""
    pass

class AllowanceError(ArbitrageError):
    """Raised when token allowance is insufficient."""
    pass

class PricingError(ArbitrageError):
    """Raised when price calculation fails."""
    pass

class OrderError(ArbitrageError):
    """Raised when order management fails."""
    pass

class EventError(ArbitrageError):
    """Raised when event handling fails."""
    pass

class CallbackError(ArbitrageError):
    """Raised when callback execution fails."""
    pass

class SyncError(ArbitrageError):
    """Raised when synchronization fails."""
    pass

class QueueError(ArbitrageError):
    """Raised when queue operations fail."""
    pass

class RetryError(ArbitrageError):
    """Raised when retry mechanism fails."""
    pass

class CircuitError(ArbitrageError):
    """Raised when circuit breaker operations fail."""
    pass

class ThrottleError(ArbitrageError):
    """Raised when rate limiting is exceeded."""
    pass

class ProxyError(ArbitrageError):
    """Raised when proxy operations fail."""
    pass

class UpgradeableError(ArbitrageError):
    """Raised when upgradeable contract operations fail."""
    pass

class StorageError(ArbitrageError):
    """Raised when storage operations fail."""
    pass

class EncodingError(ArbitrageError):
    """Raised when encoding/decoding fails."""
    pass

class ABIError(ArbitrageError):
    """Raised when ABI operations fail."""
    pass

class BytecodeError(ArbitrageError):
    """Raised when bytecode operations fail."""
    pass
