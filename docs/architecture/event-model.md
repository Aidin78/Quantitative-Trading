# Event Model — مدل رویداد رسمی

> Event Layer نحوه **انتشار** را تعریف می‌کند. این سند **چه eventهایی** وجود دارند، lifecycle آن‌ها، و schema استاندارد را مشخص می‌کند.
>
> مرتبط: [event-layer.md](./event-layer.md) | [time-semantics.md](./time-semantics.md) | [replay-engine.md](./replay-engine.md)

## چرا Event Model جدا از Event Layer؟

| مفهوم | سؤال |
|-------|------|
| **Event Layer** | event چطور publish و consume می‌شود؟ |
| **Event Model** | event **چیست**، از کجا می‌آید، به کجا می‌رود؟ |

بدون Event Model رسمی، replay، forensic debugging و causal analysis ممکن نیست.

## Taxonomy — چهار خانواده رویداد

```
MarketEvent     →  داده و ویژگی‌های بازار
SignalEvent     →  نظر Providerها
DecisionEvent   →  خروجی Engine
ExecutionEvent  →  اثر تصمیم (شبیه‌سازی / اعلان / معامله)
```

### نمودار lifecycle یک cycle

```
MarketEvent(CandleReceived)
    │
    ▼
MarketEvent(FeatureSetBuilt)
    │
    ├──► SignalEvent(ProviderOpinion) × N
    │         │
    │         ▼
    └────► DecisionEvent(DecisionMade)
              │
              ├──► DecisionEvent(DecisionApproved)
              │         │
              │         ▼
              │    ExecutionEvent(OrderIntentCreated)
              │         → FillReceived → PositionOpened/Closed
              │    ExecutionEvent(SignalPublished)    ← notification only
              │
              └──► DecisionEvent(DecisionRejected)
```

## Envelope استاندارد

همه eventها از یک envelope مشترک پیروی می‌کنند:

```python
@dataclass(frozen=True)
class EventEnvelope:
    event_id: str                    # UUID — یکتا در کل سیستم
    event_family: Literal["market", "signal", "decision", "execution"]
    event_type: str                  # e.g. "FeatureSetBuilt"
    schema_version: str              # e.g. "v1"

    # زمان — جزئیات در time-semantics.md
    event_time: datetime             # زمان وقوع در بازار
    processing_time: datetime        # زمان پردازش در سیستم

    # trace
    correlation_id: str              # یک cycle — مثلاً cycle_btc_1h_xxx
    causation_id: str | None         # event قبلی که باعث این شد
    cycle_id: str                    # = correlation_id برای cycle

    # context
    symbol: str
    timeframe: str
    mode: Literal["validation", "live", "paper", "replay"]
    experiment_id: str | None         # governance — [governance.md](./governance.md)
    revision_id: str | None           # ConfigRevision

    payload: dict[str, Any]
```

## MarketEvent

اتفاقات مربوط به داده خام و feature.

| event_type | trigger | payload کلیدی |
|------------|---------|---------------|
| `CandleReceived` | OHLCV جدید از provider | open, high, low, close, volume |
| `FeatureSetBuilt` | FeatureBuilder.build() | feature_set_id, version, indicators, flags |
| `MarketContextDerived` | context_deriver | trend, volatility, session, atr |

```json
{
  "event_type": "FeatureSetBuilt",
  "event_family": "market",
  "event_time": "2026-07-06T10:00:00Z",
  "processing_time": "2026-07-06T10:00:01.240Z",
  "payload": {
    "feature_set_id": "fs_abc123",
    "feature_version": "v1",
    "indicators": { "rsi_14": 28.5, "ema_12": 67100 },
    "flags": { "ema_cross_bullish": true }
  }
}
```

## SignalEvent

نظر هر Provider — قبل از تصمیم Engine.

| event_type | trigger | payload کلیدی |
|------------|---------|---------------|
| `ProviderOpinion` | Provider.analyze() | provider_id, side, confidence, rationale |
| `ProviderSkipped` | enabled=false یا خطا | provider_id, reason |

```python
@dataclass(frozen=True)
class ProviderRationale:
    """explainability — چرا این نظر؟"""
    summary: str                     # "RSI oversold + bullish EMA cross"
    factors: list[RationaleFactor]   # structured
    feature_refs: dict[str, float]   # {"rsi_14": 28.5}

@dataclass(frozen=True)
class RationaleFactor:
    name: str                        # "rsi_oversold"
    weight: float                    # 0.0–1.0
    direction: Literal["bullish", "bearish", "neutral"]
    evidence: str                    # "rsi_14 < 30"
```

```json
{
  "event_type": "ProviderOpinion",
  "event_family": "signal",
  "payload": {
    "provider_id": "rsi_divergence",
    "side": "BUY",
    "confidence": 0.68,
    "rationale": {
      "summary": "RSI oversold with bullish divergence",
      "factors": [
        { "name": "rsi_oversold", "weight": 0.6, "direction": "bullish", "evidence": "rsi_14=28.5" }
      ],
      "feature_refs": { "rsi_14": 28.5 }
    }
  }
}
```

## DecisionEvent

خروجی Engine — تأیید یا رد.

| event_type | trigger | payload کلیدی |
|------------|---------|---------------|
| `DecisionMade` | Engine.process() — همیشه | result, decision_log |
| `DecisionApproved` | result=approved | final_signal, state_snapshot_id |
| `DecisionRejected` | result=rejected | rejection_reason, rejection_stage |
| `RiskLimitBreached` | RiskManager رد کرد | limit_name, current, threshold |

```json
{
  "event_type": "DecisionRejected",
  "event_family": "decision",
  "payload": {
    "decision_id": "dec_abc123",
    "rejection_stage": "risk_manager",
    "rejection_reason": "daily_drawdown_limit",
    "decision_log": {
      "market_filter": { "passed": true },
      "aggregation": { "side": "BUY", "confidence": 0.72 },
      "risk_check": { "passed": false, "reason": "daily_drawdown_limit" }
    },
    "state_snapshot_id": "state_snap_001"
  }
}
```

**نکته:** `state_snapshot_id` به snapshot وضعیت در لحظه تصمیم اشاره می‌کند — برای replay و forensic.

## ExecutionEvent

اثر تصمیم تأییدشده — lifecycle کامل در [execution-model.md](./execution-model.md).

| event_type | trigger | payload کلیدی |
|------------|---------|---------------|
| `OrderIntentCreated` | DecisionApproved | `OrderIntent` |
| `OrderSubmitted` | ExecutionEngine | `order_id`, `venue` |
| `FillReceived` | simulator / exchange | `Fill`, `fill_model_id` |
| `PositionOpened` | entry fill | `position_id` |
| `PositionClosed` | exit complete | `pnl`, `exit_reason` |
| `SignalPublished` | notification handler | `channels` — **نه** trade |
| `OrderRejected` | pre-trade risk / broker | `reason`, `stage` |

**تفکیک:** `SignalPublished` (Telegram) جدا از `FillReceived` (اجرای واقعی/shim).

## State Transition در Event Model

هر DecisionEvent باید به **StateSnapshot** قبل از تصمیم اشاره کند:

```
StateSnapshot (before)
    │
    ▼
DecisionEvent
    │
    ▼
StateTransitionEvent (optional)  ← اگر state تغییر کرد
    │
    ▼
StateSnapshot (after)
```

جزئیات: [state-management.md](./state-management.md)

## Event Store Schema

```sql
-- جدول پیشنهادی event_log
CREATE TABLE event_log (
    event_id          UUID PRIMARY KEY,
    event_family      VARCHAR(20) NOT NULL,
    event_type        VARCHAR(50) NOT NULL,
    schema_version    VARCHAR(10) NOT NULL,
    event_time        TIMESTAMPTZ NOT NULL,
    processing_time   TIMESTAMPTZ NOT NULL,
    correlation_id    VARCHAR(64) NOT NULL,
    causation_id      UUID,
    symbol            VARCHAR(20),
    timeframe         VARCHAR(10),
    mode              VARCHAR(20),
    payload           JSONB NOT NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_event_log_correlation ON event_log(correlation_id);
CREATE INDEX ix_event_log_event_time ON event_log(event_time);
CREATE INDEX ix_event_log_family_type ON event_log(event_family, event_type);
```

## قرارداد نسخه‌گذاری

| تغییر | اقدام |
|-------|--------|
| فیلد جدید optional | همان schema_version |
| فیلد حذف یا rename | `schema_version` جدید (v2) |
| event_type جدید | اضافه بدون breaking change |
| تغییر semantics | event_type جدید + deprecate قدیم |

## Mapping به WebSocket / API

| Event Model | WebSocket event | REST |
|-------------|-----------------|------|
| `DecisionApproved` | `decision.created` | `GET /decisions/{id}` |
| `DecisionRejected` | `decision.rejected` | `GET /decisions/{id}` |
| `SignalPublished` | `signal.new` | `GET /signals/{id}` |
| `FeatureSetBuilt` | — | `GET /features/snapshot` |
| `ProviderOpinion` | — | در `decision.provider_signals` |

## Anti-Patterns

| Anti-Pattern | درست |
|--------------|------|
| event_type string آزاد بدون enum | `EventType` enum + schema registry |
| فقط Decision ذخیره شود | کل chain: Market → Signal → Decision → Execution |
| event_time = processing_time | تفکیک صریح — [time-semantics.md](./time-semantics.md) |
| rationale در metadata بدون schema | `ProviderRationale` structured |
| replay بدون event_log | Event Store از فاز validation |

## جمع‌بندی

```
Event Model = زبان مشترک سیستم
Event Layer = مکانیزم انتشار
Event Store = حافظه برای replay
Time Semantics = معنای زمان هر event
State Snapshots = context تصمیم در لحظه وقوع
```
