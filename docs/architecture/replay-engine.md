# Replay Engine — موتور بازپخش

> Replay Engine سیستمی **مستقل** از Validation Harness است که eventها، state و تصمیم‌ها را برای forensic debugging و causal analysis بازپخش می‌کند.
>
> مرتبط: [event-model.md](./event-model.md) | [state-management.md](./state-management.md) | [validation harness](../backend/backtesting.md)

## تفاوت Replay و Validation

| | Validation Harness | Replay Engine |
|---|-------------------|---------------|
| **هدف** | سنجش کیفیت استراتژی (PnL، metrics) | بازسازی دقیق رفتار سیستم |
| **ورودی** | OHLCV + config | `event_log` + snapshots |
| **خروجی** | گزارش عملکرد | همان decision chain + diff |
| **تغییر کد** | ممکن است re-run با engine جدید | می‌تواند strict یا re-interpret باشد |
| **کاربر** | quant / strategy dev | engineer / debugger |

```
Validation:  OHLCV ──► Runtime ──► metrics
Replay:      event_log ──► ReplayEngine ──► forensic report / diff
```

## حالت‌های Replay

### 1. Strict Replay

eventها به ترتیب `event_time` بازپخش می‌شوند؛ **هیچ محاسبه مجددی** انجام نمی‌شود.

- استفاده: audit، «دقیقاً چه اتفاقی افتاد؟»
- خروجی: timeline، causal graph

### 2. Re-execute Replay

از `MarketEvent` شروع، Feature Builder و Engine **دوباره** اجرا می‌شوند.

- استفاده: «اگر کد جدید بود، تصمیم عوض می‌شد؟»
- نیاز: [Feature Store](./feature-store.md) با همان version
- خروجی: `DecisionDiff` (expected vs actual)

### 3. Partial Replay

فقط یک `correlation_id` (یک cycle) یا بازه زمانی.

```
GET /replay/cycles/{correlation_id}
GET /replay/range?from=&to=&symbol=
```

## معماری

```
┌─────────────────┐
│   Event Store   │  event_log
└────────┬────────┘
         │
┌────────▼────────┐     ┌──────────────────┐
│  Replay Engine  │────►│ State Rebuilder  │  state_snapshots
└────────┬────────┘     └──────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
 Timeline   Diff Engine
    │         │
    ▼         ▼
 Dashboard  API / CLI
```

## ReplayEngine API (مفهومی)

```python
class ReplayEngine:
    def replay_cycle(self, correlation_id: str, mode: ReplayMode) -> ReplayResult: ...
    def replay_range(
        self,
        symbol: str,
        from_time: datetime,
        to_time: datetime,
        mode: ReplayMode,
    ) -> ReplayResult: ...

@dataclass
class ReplayResult:
    correlation_ids: list[str]
    events: list[EventEnvelope]
    decisions: list[DecisionEvent]
    state_timeline: list[StateSnapshot]
    diffs: list[DecisionDiff] | None      # فقط در re-execute
    causal_graph: CausalGraph
```

## Causal Graph

برای هر `DecisionEvent`، زنجیره علت:

```
CandleReceived
  └─► FeatureSetBuilt
        └─► ProviderOpinion (rsi_divergence)
        └─► ProviderOpinion (ema_cross)
              └─► DecisionMade
                    └─► DecisionRejected (risk: daily_drawdown)
```

ذخیره `causation_id` در envelope این گراف را می‌سازد.

## DecisionDiff

```python
@dataclass
class DecisionDiff:
    correlation_id: str
    event_time: datetime
    recorded: DecisionEvent      # از event_log
    recomputed: DecisionEvent | None
    match: bool
    diff_fields: dict[str, tuple[Any, Any]]
```

## UI / API

| Endpoint | توضیح |
|----------|--------|
| `POST /replay/cycle/{correlation_id}` | بازپخش یک cycle |
| `POST /replay/range` | بازه زمانی |
| `GET /replay/{job_id}/timeline` | timeline رویدادها |
| `GET /replay/{job_id}/causal/{decision_id}` | گراف علت |
| `WS replay.progress` | پیشرفت job |

صفحه پیشنهادی در dashboard: **Forensic / Replay** (کنار Decision Monitor).

## پیش‌نیازها

1. [Event Model](./event-model.md) — event_log پر از Market تا Execution
2. [State Management](./state-management.md) — snapshots در هر تصمیم
3. [Time Semantics](./time-semantics.md) — event_time برای ordering
4. [Feature Store](./feature-store.md) — برای re-execute بدون drift

## فازبندی

| فاز | قابلیت |
|-----|--------|
| MVP | strict replay از event_log + timeline API |
| v2 | partial replay per correlation_id |
| v3 | re-execute + DecisionDiff |
| v4 | causal graph UI |
