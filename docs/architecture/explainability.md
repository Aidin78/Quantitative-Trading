# Explainability — شفافیت Provider و تصمیم

> مدل خروجی Provider و سطح explainability تصمیم‌ها به‌صورت structured تعریف می‌شود. Risk Engine با state و event layer عمیقاً یکپارچه است.
>
> مرتبط: [event-model.md](./event-model.md) | [state-management.md](./state-management.md) | [core-concepts.md](../backend/core-concepts.md)

## لایه‌های Explainability

```
Layer 1: Provider Rationale     → چرا Provider این نظر را داد؟
Layer 2: Aggregation Log        → Engine چطور نظرها را ترکیب کرد؟
Layer 3: Risk Verdict           → چرا risk تأیید/رد کرد؟
Layer 4: Final Decision Record  → خروجی یکپارچه برای UI/API
```

## Provider Output Model

Provider فقط `StrategySignal` برنمی‌گرداند؛ `ProviderOpinion` کامل:

```python
@dataclass(frozen=True)
class StrategySignal:
  provider_id: str
  side: Literal["BUY", "SELL", "HOLD"]
  confidence: float              # 0.0 – 1.0
  rationale: ProviderRationale
  feature_set_id: str            # ارجاع به Feature Store
  valid_until_event_time: datetime | None

@dataclass(frozen=True)
class ProviderRationale:
  summary: str
  factors: tuple[RationaleFactor, ...]
  feature_refs: dict[str, float]
  metadata: dict[str, Any]       # provider-specific، JSON-serializable
```

### قرارداد Provider

- **ورودی:** `FeatureSet` + `MarketContext` (نه OHLCV خام)
- **خروجی:** `StrategySignal` با `rationale` اجباری برای BUY/SELL
- **HOLD:** confidence پایین + factors توضیح «چرا ورود نیست»

## Decision Log (Engine)

```python
@dataclass(frozen=True)
class DecisionLog:
  market_filter: StageResult
  provider_signals: tuple[StrategySignal, ...]
  aggregation: AggregationResult
  risk_check: RiskVerdict
  state_snapshot_id: str

@dataclass(frozen=True)
class StageResult:
  passed: bool
  reason: str | None
  details: dict[str, Any]

@dataclass(frozen=True)
class AggregationResult:
  method: str                    # "weighted_vote", "unanimous", ...
  side: str
  confidence: float
  weights: dict[str, float]      # provider_id → weight
  dissent: list[str]             # providerهای مخالف
```

## Risk Engine — یکپارچگی با State و Events

Risk فقط تابع روی signal نیست؛ **read-only consumer** از `StateSnapshot`. مرز enforceable: [state-risk-contract.md](../architecture/state-risk-contract.md).

```
StateStore.get_risk() + get_portfolio()
        │
        ▼
RiskManager.evaluate(signal, state_snapshot)
        │
        ├── pass  → DecisionApproved
        └── fail  → DecisionRejected + RiskLimitBreached event
```

```python
@dataclass(frozen=True)
class RiskVerdict:
  passed: bool
  checks: tuple[RiskCheckResult, ...]
  state_snapshot_id: str
  risk_state_version: int

@dataclass(frozen=True)
class RiskCheckResult:
  check_name: str                # "daily_drawdown", "max_positions", ...
  passed: bool
  current_value: float
  threshold: float
  message: str
```

### Risk Events

| event | زمان |
|-------|------|
| `RiskLimitBreached` | هنگام رد تصمیم |
| `RiskStateUpdated` | پس از StateTransition (مثلاً بسته شدن position) |

## API / UI Contract

`GET /decisions/{id}` باید برگرداند:

```json
{
  "decision_id": "dec_abc",
  "result": "rejected",
  "event_time": "...",
  "decision_time": "...",
  "explainability": {
    "summary": "Rejected: daily drawdown limit",
    "provider_signals": [...],
    "aggregation": { "side": "BUY", "confidence": 0.72 },
    "risk_check": {
      "passed": false,
      "checks": [
        { "check_name": "daily_drawdown", "passed": false, "current_value": 5.2, "threshold": 5.0 }
      ]
    },
    "state_snapshot_id": "snap_001",
    "causal_chain_url": "/replay/cycle/corr_xyz/causal/dec_abc"
  }
}
```

صفحه **Decision Monitor** — نمایش لایه‌های ۱–۴ + لینک به Replay.

## Anti-Patterns

| Anti-Pattern | درست |
|--------------|------|
| `reason: string` آزاد | `DecisionLog` structured |
| risk فقط در Engine inline | `RiskManager` + `RiskVerdict` |
| UI مستقیم از Telegram parse کند | از `explainability` API |
| Provider بدون feature_refs | ارجاع به FeatureSetRecord |
