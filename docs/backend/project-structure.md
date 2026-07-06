# ساختار پروژه بک‌اند

> **Config:** فایل‌های `config/` در **root monorepo** هستند (`../config/`) — مشترک بین Docker، backend و scripts.

## درخت پوشه‌ها (monorepo)

```
quantitative-trading/
├── config/                     # تنظیمات مشترک — root
│   ├── settings.yaml
│   ├── engine.yaml
│   ├── features.yaml
│   └── providers/
├── data/historical/            # CSV
├── backend/
```

## درخت backend

```
backend/
├── alembic/                    # Database migrations
│   ├── versions/
│   └── env.py
├── scripts/
│   ├── run_validation.py       # CLI validation harness
│   ├── run_experiment.py       # CLI A/B experiment
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
│   │   │   ├── event.py          # EventEnvelope, EventBus
│   │   │   ├── execution.py      # OrderIntent, Order, Fill
│   │   │   ├── governance.py     # ConfigRevision, Experiment
│   │   │   ├── state.py          # PortfolioState, RiskState, StateSnapshot
│   │   │   ├── time.py           # Clock protocol
│   │   │   ├── rationale.py      # ProviderRationale, RiskVerdict
│   │   │   ├── provider.py
│   │   │   └── data.py
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
│   │   ├── store.py            # FeatureStore — put/get/versioned
│   │   ├── context_deriver.py
│   │   └── indicators/
│   │       ├── rsi.py
│   │       ├── ema.py
│   │       └── atr.py
│   ├── runtime/                # Phase 3
│   │   ├── platform_runtime.py
│   │   ├── scheduler.py
│   │   └── clocks.py           # WallClock, SimulatedClock
│   ├── state/                  # State Management
│   │   ├── store.py            # StateStore protocol
│   │   ├── in_memory_store.py
│   │   ├── postgres_store.py
│   │   └── transitions.py
│   ├── events/                 # Domain events + EventBus
│   │   ├── envelopes.py        # EventEnvelope + event types
│   │   ├── event_bus.py
│   │   ├── event_store.py      # event_log persistence
│   │   ├── in_memory_bus.py
│   │   ├── redis_bus.py
│   │   └── handlers/
│   │       ├── database_handler.py
│   │       ├── websocket_handler.py
│   │       ├── telegram_handler.py   # SignalPublished only
│   │       ├── execution_log_handler.py
│   │       └── metrics_handler.py
│   ├── data/                   # MarketDataProvider adapters
│   │   ├── csv_provider.py
│   │   └── live_provider.py
│   ├── execution/              # Execution Model
│   │   ├── engine.py           # ExecutionEngine protocol
│   │   ├── simulated.py        # SimulatedExecutionEngine + FillModel
│   │   ├── risk_gate.py        # ExecutionRiskGate (pre-trade)
│   │   └── models.py           # OrderIntent, Order, Fill
│   ├── governance/             # Experiment Management
│   │   ├── revisions.py        # ConfigRevision
│   │   ├── experiments.py
│   │   ├── comparison.py       # A/B ExperimentComparison
│   │   └── live_gate.py        # LiveGovernanceGate
│   ├── validation/             # Phase 4
│   │   ├── harness.py
│   │   └── metrics.py          # PnL از ExecutionEvent
│   ├── replay/                 # Replay Engine (مستقل از validation)
│   │   ├── engine.py
│   │   ├── timeline.py
│   │   ├── causal_graph.py
│   │   └── diff.py
│   ├── providers/              # Phase 5 — plug-in
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── ema_crossover.py
│   │   └── rsi_divergence.py
│   ├── api/
│   │   ├── v1/
│   │   │   ├── decisions.py    # ★ اولویت — تمام تصمیمات + explainability
│   │   │   ├── replay.py       # forensic replay API
│   │   │   ├── engine.py       # config + stats
│   │   │   ├── experiments.py  # governance API
│   │   │   ├── validation.py
│   │   │   ├── signals.py
│   │   │   ├── providers.py
│   │   │   ├── live.py
│   │   │   └── auth.py
│   │   └── websocket/
│   └── db/
│       └── repositories/
│           ├── decision.py
│           ├── event_log.py
│           ├── feature_set.py
│           ├── state_snapshot.py
│           ├── experiment.py
│           ├── order.py
│           ├── fill.py
│           └── provider.py
├── tests/
│   ├── mocks/
│   │   └── mock_providers.py   # تست Engine بدون provider واقعی
│   ├── unit/
│   │   ├── test_features.py    # snapshot FeatureSet
│   │   ├── test_engine.py
│   │   └── test_providers.py
│   └── integration/
│       ├── test_events.py
│       ├── test_runtime.py
│       └── test_validation.py
├── pyproject.toml
└── .env.example
```

## ترتیب وابستگی (مهم)

```
contracts → engine → features → state → runtime → events → validation → replay → providers → api
                         ↑
                    mock FeatureSet
```

**قوانین وابستگی:**
- `engine/` — بدون import از `providers/` و `features/`
- `features/` — بدون import از `providers/` و `engine/`
- `state/` — بدون import از `providers/`؛ Engine فقط snapshot می‌خواند
- `providers/` — فقط `FeatureSet` می‌گیرد، نه OHLCV خام
- `runtime/` orchestration می‌کند؛ قبل از Engine، `StateStore.snapshot()` می‌گیرد
- `events/handlers/` تنها محل side-effectها
- `replay/` فقط از `event_log` + `feature_store` + `state_snapshots` می‌خواند

## مسئولیت هر ماژول

### `src/core/contracts/`

قراردادهای ثابت — شامل `features.py` برای `FeatureSet`.

### `src/features/`

Feature Builder — **تنها** جایی که اندیکاتور محاسبه می‌شود. OHLCV → `FeatureSet` + `MarketContext`.

### `src/engine/`

قلب سیستم — `StrategySignal` + `MarketContext` → `Decision`.

### `src/runtime/`

`PlatformRuntime` — data → **features** → providers → engine → event_bus.

### `src/execution/`

Execution Model — Order/Fill lifecycle. جزئیات: [execution-model.md](../architecture/execution-model.md).

### `src/governance/`

Experiment Management — ConfigRevision، A/B. جزئیات: [governance.md](../architecture/governance.md).

### `src/state/`

State Management مرکزی — `PortfolioState`, `RiskState`, `StateSnapshot`. جزئیات: [state-management.md](../architecture/state-management.md).

### `src/replay/`

Replay Engine — strict و re-execute replay. جزئیات: [replay-engine.md](../architecture/replay-engine.md).

### `src/events/`

Event Layer — `DomainEvent`, `EventBus` و handlerها. Runtime فقط event publish می‌کند؛ DB، WebSocket، Telegram و Simulation در handlerها انجام می‌شوند.

### `src/validation/`

Harness برای iterate تاریخ — **نه** logic جدا از Runtime.

### `src/providers/`

SignalProviderهای plug-in — آخرین لایه اضافه‌شده.

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
