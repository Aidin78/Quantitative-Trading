# Time Semantics — معنای زمان

> زمان در سیستم معاملاتی یک مفهوم مستقل است. تفکیک `event_time`، `processing_time` و `decision_time` برای latency، causality و replay ضروری است.
>
> مرتبط: [event-model.md](./event-model.md) | [state-management.md](./state-management.md) | [replay-engine.md](./replay-engine.md)

## سه بعد زمان

| مفهوم | تعریف | مثال |
|-------|--------|------|
| **event_time** | زمان وقوع در بازار (close کندل) | `2026-07-06T10:00:00Z` |
| **processing_time** | زمان پردازش در سیستم | `2026-07-06T10:00:01.240Z` |
| **decision_time** | لحظه نهایی شدن تصمیم Engine | `2026-07-06T10:00:01.890Z` |

```
event_time          processing_time              decision_time
    │                      │                           │
    ▼                      ▼                           ▼
[Candle closes]    [Feature built]              [Decision approved]
```

## قوانین

1. **Ordering در replay** — همیشه بر اساس `event_time`؛ در تساوی، `processing_time`
2. **Latency** — `processing_time - event_time` (ingestion lag)
3. **Decision latency** — `decision_time - event_time` (end-to-end)
4. **State `as_of`** — `PortfolioState.as_of_event_time` = آخرین event_time اعمال‌شده

## Clock Abstraction

```python
class Clock(Protocol):
    def now_event_time(self) -> datetime: ...
    def now_processing_time(self) -> datetime: ...

class WallClock:
    """live — processing_time = UTC now"""

class SimulatedClock:
    """validation / replay — event_time از داده؛ processing_time قابل کنترل"""
```

در validation، `processing_time` می‌تواند برابر `event_time` باشد (بدون شبیه‌سازی lag) یا با offset ثابت برای تست.

## Timestamps در مدل‌ها

| موجودیت | فیلدهای زمان |
|---------|--------------|
| `EventEnvelope` | event_time, processing_time |
| `DecisionEvent` | + decision_time در payload |
| `FeatureSetRecord` | event_time, processing_time |
| `StateSnapshot` | as_of_event_time, as_of_processing_time |
| `PositionState` | entry_time (event_time) |

## Watermark (Live)

برای جلوگیری از تصمیم روی داده ناقص:

```
watermark = max(event_time) - allowed_lateness
```

تا وقتی `event_time <= watermark`، cycle کامل در نظر گرفته می‌شود. در MVP validation، watermark لازم نیست (داده batch کامل است).

## Causality

```
causation_id  →  event قبلی
correlation_id  →  یک cycle (معمولاً یک bar)
```

تحلیل علت: «تصمیم در decision_time X به خاطر FeatureSetBuilt در processing_time Y روی event_time Z»

## Metrics

| متریک | فرمول |
|-------|--------|
| `ingestion_lag_ms` | processing_time - event_time (CandleReceived) |
| `feature_build_ms` | FeatureSetBuilt.processing - CandleReceived.processing |
| `decision_e2e_ms` | decision_time - event_time |
| `provider_max_ms` | max(ProviderOpinion.processing) - cycle start |

## Anti-Patterns

| Anti-Pattern | درست |
|--------------|------|
| `datetime.now()` پراکنده | Clock inject شده |
| فقط یک timestamp | سه بعد صریح |
| replay با processing_time order | order با event_time |
