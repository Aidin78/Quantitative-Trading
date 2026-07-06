# Feature Store — ذخیره و نسخه‌بندی Feature

> Feature Builder feature تولید می‌کند؛ Feature Store آن را **ذخیره**، **نسخه‌بندی** و **قابل بازپخش** می‌کند تا اختلاف backtest/live از بین برود.
>
> مرتبط: [feature-builder.md](./feature-builder.md) | [replay-engine.md](./replay-engine.md) | [event-model.md](./event-model.md)

## مشکل بدون Feature Store

| وضعیت فعلی | ریسک |
|------------|------|
| Feature لحظه‌ای در memory | replay غیرممکن |
| تغییر config بدون version | تصمیم‌های قدیمی غیرقابل reproduce |
| محاسبه مجدد در live | drift عددی با validation |

## اصول

1. هر `FeatureSetBuilt` یک **رکورد immutable** در store
2. `feature_version` + `config_hash` در metadata
3. lookup با `(symbol, timeframe, event_time, feature_version)`
4. Feature Builder **نویسنده**؛ Engine/Providers/Replay **خواننده**

## مدل داده

```python
@dataclass(frozen=True)
class FeatureSetRecord:
    feature_set_id: str
    symbol: str
    timeframe: str
    event_time: datetime
    processing_time: datetime
    feature_version: str           # e.g. "v1"
    config_hash: str               # hash of features.yaml
    indicators: dict[str, float]
    flags: dict[str, bool]
    market_context: MarketContext
    schema_version: str
```

## Feature Versioning

| سطح | مثال | زمان bump |
|-----|------|-----------|
| `schema_version` | v1 → v2 | تغییر ساختار FeatureSetRecord |
| `feature_version` | v1 → v2 | اضافه/حذف indicator در config |
| `config_hash` | abc123 | هر تغییر در `features.yaml` |

```yaml
# config/features.yaml
version: v2
indicators:
  rsi:
  period: 14
  ema:
  periods: [12, 26]
```

## جریان نوشتن

```
OHLCV
  │
  ▼
FeatureBuilder.build()
  │
  ├──► FeatureSet (in-memory برای cycle فعلی)
  │
  └──► FeatureStore.put(FeatureSetRecord)
            │
            └──► MarketEvent(FeatureSetBuilt) با feature_set_id
```

## جریان خواندن

| مصرف‌کننده | حالت |
|------------|------|
| Signal Providers | همان cycle — از memory |
| Replay (strict) | FeatureStore.get(feature_set_id) |
| Replay (re-execute) | build مجدد + compare با stored |
| API / Dashboard | GET /features/snapshot |

## Persistence

```sql
CREATE TABLE feature_sets (
    feature_set_id    UUID PRIMARY KEY,
    symbol            VARCHAR(20) NOT NULL,
    timeframe         VARCHAR(10) NOT NULL,
    event_time        TIMESTAMPTZ NOT NULL,
    processing_time   TIMESTAMPTZ NOT NULL,
    feature_version   VARCHAR(20) NOT NULL,
    config_hash       VARCHAR(64) NOT NULL,
    indicators        JSONB NOT NULL,
    flags             JSONB NOT NULL,
    market_context    JSONB NOT NULL,
    schema_version    VARCHAR(10) NOT NULL,
    UNIQUE (symbol, timeframe, event_time, feature_version)
);

CREATE INDEX ix_feature_sets_lookup
    ON feature_sets(symbol, timeframe, event_time, feature_version);
```

TimescaleDB برای retention و compression روی `event_time` مناسب است.

## FeatureStore API (مفهومی)

```python
class FeatureStore(Protocol):
    def put(self, record: FeatureSetRecord) -> None: ...
    def get(self, feature_set_id: str) -> FeatureSetRecord: ...
    def get_at(
        self,
        symbol: str,
        timeframe: str,
        event_time: datetime,
        feature_version: str,
    ) -> FeatureSetRecord | None: ...
```

## Drift Detection

در re-execute replay:

```python
stored = feature_store.get_at(symbol, tf, event_time, version)
rebuilt = feature_builder.build(candles, version=version)
drift = compare_features(stored.indicators, rebuilt.indicators, tolerance=1e-6)
```

اگر drift باشد → هشدار در گزارش replay (علت احتمالی اختلاف تصمیم).

## Anti-Patterns

| Anti-Pattern | درست |
|--------------|------|
| فقط آخرین feature در Redis | immutable records per bar |
| version فقط در git | `feature_version` + `config_hash` در DB |
| Provider indicator محاسبه کند | فقط Feature Builder |
