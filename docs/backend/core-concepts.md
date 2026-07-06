# مفاهیم هسته (Core Concepts)

> استراتژی = `SignalProvider`. تصمیم نهایی فقط در `DecisionEngine`.
>
> زیرساخت مفهومی: [event-model.md](../architecture/event-model.md) | [state-management.md](../architecture/state-management.md) | [explainability.md](../architecture/explainability.md)

## Decision — خروجی Engine

```python
@dataclass
class Decision:
    result: Literal["approved", "rejected"]
    final_signal: FinalSignal | None      # فقط اگر approved
    rejection_reason: str | None          # فقط اگر rejected
    decision_log: DecisionLog             # همیشه — شفافیت کامل
    timestamp: datetime
```

## مدل‌های دامنه

### StrategySignal

خروجی هر **SignalProvider** — ورودی Engine، نه محصول نهایی.

```python
@dataclass(frozen=True)
class StrategySignal:
    provider_id: str
    symbol: str
    side: Literal["BUY", "SELL", "HOLD"]
    confidence: float              # 0.0 – 1.0
    rationale: ProviderRationale   # اجباری برای BUY/SELL — explainability
    feature_set_id: str            # ارجاع به Feature Store
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    timeframe: str
    event_time: datetime
    valid_until_event_time: datetime | None
```

**قوانین:**
- `HOLD` یعنی استراتژی نظری ندارد — در aggregation نادیده گرفته می‌شود
- `confidence` توسط خود Provider محاسبه می‌شود
- `rationale` structured است — نه `metadata` آزاد — جزئیات: [explainability.md](../architecture/explainability.md)

### FinalSignal

خروجی Decision Engine — آماده ارسال.

```python
@dataclass
class FinalSignal:
    id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    risk_reward: float
    timeframe: str
    timestamp: datetime
    contributing_strategies: list[str]
    market_context: MarketContext
    decision_log: dict[str, Any]
```

### MarketContext

```python
@dataclass
class MarketContext:
    symbol: str
    timeframe: str
    current_price: float
    trend: Literal["UP", "DOWN", "SIDEWAYS"]
    volatility: Literal["LOW", "NORMAL", "HIGH"]
    atr: float
    atr_pct: float                 # ATR / price * 100
    session: Literal["ASIA", "EUROPE", "US", "OVERLAP"]
    timestamp: datetime
```

### Trade (بک‌تست)

```python
@dataclass
class Trade:
    signal_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    exit_reason: Literal["TP", "SL", "SIGNAL", "TIMEOUT"]
```

---

## FeatureSet

خروجی **Feature Builder** — ورودی **Signal Provider**.

```python
@dataclass(frozen=True)
class FeatureSet:
    symbol: str
    timeframe: str
    timestamp: datetime
    version: str
    close: float
    indicators: dict[str, float]   # {"rsi_14": 28.5, "ema_12": 67100}
    flags: dict[str, bool]         # {"ema_cross_bullish": True}
    levels: dict[str, float]       # {"support": 66000}
```

**قانون:** Provider به `FeatureSet` دسترسی دارد — نه OHLCV خام.

---

## SignalProvider (استراتژی)

```python
class SignalProvider(Protocol):
    provider_id: str
    enabled: bool
    weight: float

    def analyze(self, features: FeatureSet,
                context: MarketContext) -> StrategySignal: ...
```

**قوانین Provider:**
- فقط **تفسیر** features — نه محاسبه اندیکاتور
- فقط `StrategySignal` برمی‌گرداند
- حق دسترسی به Telegram، DB، Risk ندارد

### BaseSignalProvider

```python
class BaseSignalProvider(ABC):
    def __init__(self, config: dict):
        self.params = config.get("params", {})
        self.enabled = config.get("enabled", True)
        self.weight = config.get("weight", 1.0)

    @abstractmethod
    def analyze(self, features: FeatureSet,
                context: MarketContext) -> StrategySignal: ...
```

---

## BaseStrategy (نام قدیمی — deprecated)

از `SignalProvider` / `BaseSignalProvider` استفاده کنید.

---

## Decision Engine

### Pipeline

```
Input: list[StrategySignal] + MarketContext
  │
  ▼
[1] MarketFilter.check(context) → pass / reject
  │
  ▼
[2] Aggregator.combine(signals) → consensus side + confidence
  │
  ▼
[3] ConfidenceFilter → min threshold
  │
  ▼
[4] RiskManager.validate(signal, portfolio_state) → pass / reject
  │
  ▼
[5] FinalSignalBuilder.build() → FinalSignal
```

### MarketFilter

شرایط نمونه:

| شرط | توضیح |
|-----|--------|
| `volatility != LOW` | در نوسان خیلی کم سیگنال نده |
| `session in allowed_sessions` | فقط سشن‌های فعال |
| `atr_pct > min_atr` | حداقل نوسان برای معامله |

### Aggregator

روش‌های ترکیب:

| روش | توضیح |
|-----|--------|
| **Majority Vote** | حداقل N استراتژی هم‌جهت |
| **Weighted Average** | confidence × weight هر استراتژی |
| **Unanimous** | همه باید موافق باشند (سخت‌گیرانه) |

پیشنهاد پیش‌فرض: **Majority Vote** + **Weighted confidence**.

```python
def aggregate(signals: list[StrategySignal]) -> AggregatedResult:
    active = [s for s in signals if s.side != "HOLD"]
    buy = [s for s in active if s.side == "BUY"]
    sell = [s for s in active if s.side == "SELL"]

    if len(buy) >= min_agreeing and len(buy) > len(sell):
        confidence = weighted_avg_confidence(buy)
        return AggregatedResult(side="BUY", confidence=confidence, ...)
    # ...
```

### RiskManager

| قانون | پارامتر |
|-------|---------|
| حداکثر drawdown روزانه | `max_daily_drawdown_pct` |
| حداکثر سیگنال در روز | `max_signals_per_day` |
| حداقل confidence | `min_confidence` |
| حداقل R:R | `min_risk_reward` |
| حداکثر exposure | `max_position_size_pct` |

```python
class RiskManager:
    def evaluate(
        self,
        signal: AggregatedResult,
        snapshot: StateSnapshot,
    ) -> RiskVerdict:
        risk = snapshot.risk
        portfolio = snapshot.portfolio
        # هر check → RiskCheckResult در verdict.checks
        ...
```

`RiskVerdict` structured است — جزئیات: [explainability.md](../architecture/explainability.md).

---

## MarketDataProvider

```python
class MarketDataProvider(ABC):
    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str,
                  start: datetime, end: datetime) -> pd.DataFrame:
        """ستون‌ها: timestamp, open, high, low, close, volume"""
        ...

    @abstractmethod
    def get_latest(self, symbol: str, timeframe: str,
                   limit: int = 200) -> pd.DataFrame:
        ...
```

DataFrame استاندارد:

| ستون | نوع |
|------|-----|
| `timestamp` | datetime (index) |
| `open` | float |
| `high` | float |
| `low` | float |
| `close` | float |
| `volume` | float |

---

## State Management (لایو و validation)

وضعیت از طریق `StateStore` مرکزی مدیریت می‌شود — نه پراکنده در handlers.

```python
@dataclass(frozen=True)
class PortfolioState:
    portfolio_id: str
    mode: Literal["validation", "live", "paper", "replay"]
    equity: float
    cash: float
    open_positions: tuple[PositionState, ...]
    realized_pnl: float
    version: int
    as_of_event_time: datetime

@dataclass(frozen=True)
class RiskState:
    daily_pnl: float
    daily_drawdown_pct: float
    open_exposure_pct: float
    consecutive_losses: int
    breached_limits: tuple[str, ...]
    version: int
```

جزئیات کامل: [state-management.md](../architecture/state-management.md).

---

## Exception Hierarchy

```python
class TradingPlatformError(Exception): ...

class StrategyError(TradingPlatformError): ...
class DataProviderError(TradingPlatformError): ...
class RiskRejectedError(TradingPlatformError): ...
class BacktestError(TradingPlatformError): ...
```

---

## Config Loading

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    telegram_bot_token: str
    telegram_channel_id: str
    jwt_secret: str

    class Config:
        env_file = ".env"
```

استراتژی‌ها و risk از YAML جداگانه با `PyYAML` لود می‌شوند.
