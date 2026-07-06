class TradingPlatformError(Exception):
    """Base platform error."""


class StrategyError(TradingPlatformError):
    pass


class DataProviderError(TradingPlatformError):
    pass


class RiskRejectedError(TradingPlatformError):
    pass


class ValidationError(TradingPlatformError):
    pass


class InvalidCyclePhaseError(TradingPlatformError):
    pass


class InsufficientDataError(TradingPlatformError):
    pass
