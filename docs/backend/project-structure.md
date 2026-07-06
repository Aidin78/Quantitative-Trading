# ساختار پروژه بک‌اند

## درخت پوشه‌ها

```
backend/
├── alembic/                    # Database migrations
│   ├── versions/
│   └── env.py
├── config/
│   ├── settings.yaml
│   ├── engine.yaml             # قوانین aggregation, filter, risk
│   └── providers/              # پارامتر هر SignalProvider
│       ├── ema_crossover.yaml
│       └── rsi_divergence.yaml
├── scripts/
│   ├── run_validation.py       # CLI validation harness
│   ├── run_live.py             # CLI لایو (PlatformRuntime)
│   └── seed_db.py
├── src/
│   ├── main.py                 # FastAPI entry
│   ├── core/
│   │   ├── contracts/          # ★ قراردادهای ثابت (Phase 0)
│   │   │   ├── signal.py
│   │   │   ├── decision.py
│   │   │   ├── features.py
│   │   │   ├── context.py
│   │   │   ├── provider.py
│   │   │   ├── data.py
│   │   │   └── sink.py
│   │   ├── enums.py
│   │   └── exceptions.py
│   ├── engine/                 # ★ قلب — Phase 1
│   │   ├── decision_engine.py
│   │   ├── aggregator.py
│   │   ├── risk_manager.py
│   │   ├── market_filter.py
│   │   └── decision_log.py
│   ├── features/               # ★ Feature Builder — Phase 2
│   │   ├── builder.py
│   │   ├── registry.py
│   │   ├── context_deriver.py
│   │   └── indicators/
│   │       ├── rsi.py
│   │       ├── ema.py
│   │       └── atr.py
│   ├── runtime/                # Phase 3
│   │   ├── platform_runtime.py
│   │   ├── portfolio_tracker.py
│   │   └── scheduler.py
│   ├── data/                   # MarketDataProvider adapters
│   │   ├── csv_provider.py
│   │   └── live_provider.py
│   ├── sinks/                  # DecisionSink adapters
│   │   ├── logging_sink.py
│   │   ├── simulated_trade_sink.py
│   │   ├── database_sink.py
│   │   ├── telegram_sink.py
│   │   └── websocket_sink.py
│   ├── validation/             # Phase 4
│   │   ├── harness.py
│   │   ├── trade_simulator.py
│   │   └── metrics.py
│   ├── providers/              # Phase 5 — plug-in
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── ema_crossover.py
│   │   └── rsi_divergence.py
│   ├── api/
│   │   ├── v1/
│   │   │   ├── decisions.py    # ★ اولویت — تمام تصمیمات
│   │   │   ├── engine.py       # config + stats
│   │   │   ├── validation.py
│   │   │   ├── signals.py
│   │   │   ├── providers.py
│   │   │   ├── live.py
│   │   │   └── auth.py
│   │   └── websocket/
│   └── db/
│       └── repositories/
│           ├── decision.py
│           ├── validation.py
│           └── provider.py
├── tests/
│   ├── mocks/
│   │   └── mock_providers.py   # تست Engine بدون provider واقعی
│   ├── unit/
│   │   ├── test_features.py    # snapshot FeatureSet
│   │   ├── test_engine.py
│   │   └── test_providers.py
│   └── integration/
│       ├── test_runtime.py
│       └── test_validation.py
├── pyproject.toml
└── .env.example
```

## ترتیب وابستگی (مهم)

```
contracts → engine → features → runtime → validation → providers → api
                         ↑
                    mock FeatureSet
```

**قوانین وابستگی:**
- `engine/` — بدون import از `providers/` و `features/`
- `features/` — بدون import از `providers/` و `engine/`
- `providers/` — فقط `FeatureSet` می‌گیرد، نه OHLCV خام
- `runtime/` تنها جایی است که `data/`, `features/`, `providers/`, `engine/`, `sinks/` را orchestration می‌کند

## مسئولیت هر ماژول

### `src/core/contracts/`

قراردادهای ثابت — شامل `features.py` برای `FeatureSet`.

### `src/features/`

Feature Builder — **تنها** جایی که اندیکاتور محاسبه می‌شود. OHLCV → `FeatureSet` + `MarketContext`.

### `src/engine/`

قلب سیستم — `StrategySignal` + `MarketContext` → `Decision`.

### `src/runtime/`

`PlatformRuntime` — data → **features** → providers → engine → sink.

### `src/validation/`

Harness برای iterate تاریخ — **نه** logic جدا از Runtime.

### `src/providers/`

SignalProviderهای plug-in — آخرین لایه اضافه‌شده.

### `src/sinks/`

مقصد خروجی `Decision` — logging، simulate، telegram، db.

### `src/api/`

مشاهده‌پذیری Engine — `/decisions` مهم‌تر از `/providers`.

## فایل‌های Config

### `config/settings.yaml`

```yaml
app:
  name: "Quantitative Trading Platform"
  timezone: "Asia/Tehran"

default_symbols:
  - "BTC/USDT"
  - "ETH/USDT"

timeframes:
  - "1h"
  - "4h"

validation:
  default_start: "2024-01-01"
  min_trades: 100
```

### `config/features.yaml`

```yaml
version: v1
indicators:
  - name: rsi_14
    type: rsi
    params: { period: 14 }
  - name: ema_12
    type: ema
    params: { period: 12 }
flags:
  - name: ema_cross_bullish
    expr: "ema_12 > ema_26"
```

### `config/engine.yaml`

```yaml
engine:
  aggregation:
    min_agreeing_providers: 2
    method: weighted_majority
  filter:
    min_atr_pct: 0.3
    allowed_sessions: [EUROPE, US, OVERLAP]
  risk:
    max_daily_drawdown_pct: 5.0
    max_signals_per_day: 10
    min_confidence: 0.65
```

### `config/providers/ema_crossover.yaml`

```yaml
provider_id: ema_crossover
enabled: true
weight: 1.0
params:
  fast_period: 12
  slow_period: 26
```

## قرارداد نام‌گذاری

| نوع | قرارداد | مثال |
|-----|---------|------|
| فایل Python | snake_case | `decision_engine.py` |
| کلاس | PascalCase | `DecisionEngine` |
| تابع/متغیر | snake_case | `get_ohlcv` |
| Constant | UPPER_SNAKE | `MAX_DRAWDOWN` |
| Provider ID | snake_case | `ema_crossover` |
| API route | snake | `/api/v1/decisions` |

## Entry Points

| دستور | فایل | کاربرد |
|-------|------|--------|
| `poetry run uvicorn src.main:app` | `main.py` | API server |
| `python scripts/run_validation.py` | scripts | Validation harness |
| `python scripts/run_live.py` | scripts | PlatformRuntime + live adapters |
