# نقشه راه توسعه (Roadmap) — Architecture-Driven

> **اصل محوری:** قلب پروژه `Decision Engine` است. استراتژی‌ها فقط `SignalProvider` هستند.
> بک‌تست ابزار اعتبارسنجی Engine است، نه محصول اصلی.

مستندات مفهومی: [engine-centric.md](../architecture/engine-centric.md)

---

## مقایسه دو رویکرد

| Feature-Driven (قدیم) | Architecture-Driven (این Roadmap) |
|------------------------|-----------------------------------|
| Phase 1: Strategies + Engine | Phase 1: Contracts + Engine (با Mock Provider) |
| Phase 2: Backtest | Phase 2: Runtime Shell (یک مسیر اجرا برای همه حالت‌ها) |
| Phase 3: API | Phase 3: Validation Harness (بک‌تست = سنجش Engine) |
| Phase 4: Live | Phase 4: Providers (plug-in استراتژی‌ها) |
| — | Phase 5: Observability (API + Dashboard حول Decision) |
| — | Phase 6: Live Adapters |

---

## نمای کلی فازها

```
Phase 0          Phase 1              Phase 2              Phase 3
Contracts   →    Decision Engine  →   Feature Builder  →   Runtime + Events
(1 هفته)         (2 هفته)             (1 هفته)             (1 هفته)
                      ↓
Phase 4              Phase 5              Phase 6
Validation      →    Providers       →    Observability
(1-2 هفته)           (1 هفته)             (2 هفته)
                      ↓
                 Phase 7
                 Live Adapters
                 (1 هفته)
```

**MVP:** حدود 9–10 هفته — Engine و Feature Builder قبل از هر Provider واقعی.

---

## Phase 0: Contracts & Foundation (هفته 1)

### هدف
تعریف قراردادهای ثابت سیستم **قبل از** هر implementation.

### چرا اول؟
بدون contract، هر فاز بعدی حدس زده می‌شود. Engine و Provider باید از روز اول جدا باشند.

### Tasks

**زیرساخت:**
- [x] Monorepo: `backend/`, `frontend/`, `docs/`, `config/` (مشترک root)
- [x] Poetry, Docker Compose (postgres, redis)
- [x] ruff, pre-commit, ESLint, Prettier

**Contracts (`src/core/contracts/`):**
- [x] `signal.py` — `StrategySignal`, `ProviderRationale`, `FinalSignal`
- [x] `decision.py` — `Decision`, `DecisionResult`, `DecisionLog`, `RiskVerdict`
- [x] `features.py` — `FeatureSet`, `FeatureSetRecord`, `FeatureBuilder` protocol
- [x] `context.py` — `MarketContext`
- [x] `state.py` — `PortfolioState`, `PositionState`, `RiskState`, `StateSnapshot`
- [x] `event.py` — `EventEnvelope`, `EventBus`, event family enums
- [x] `execution.py` — `OrderIntent`, `Order`, `Fill`, `FillModel`
- [x] `governance.py` — `ConfigRevision`, `Experiment`, `ExperimentRun`
- [x] `time.py` — `Clock` protocol
- [x] `rationale.py` — `ProviderRationale`, `RiskVerdict`, `RiskCheckResult`
- [x] `provider.py` — `SignalProvider` protocol (`analyze(features, context)`)
- [x] `data.py` — `MarketDataProvider` protocol

**Config schema:**
- [x] `config/engine.yaml` — قوانین aggregation, filter, risk
- [x] `config/features.yaml` — اندیکاتورها و flags (declarative)
- [x] Pydantic settings loader

### خروجی / معیار قبولی
- [x] Contracts import می‌شوند بدون وابستگی به implementation
- [x] `EventEnvelope` با `event_time` و `processing_time` تعریف شده
- [x] `StateSnapshot` و `ProviderRationale` در contracts
- [x] هیچ فایلی در `strategies/` وجود ندارد — عمداً

مستندات مرجع: [event-model.md](../architecture/event-model.md), [state-management.md](../architecture/state-management.md), [time-semantics.md](../architecture/time-semantics.md)

---

## Phase 1: Decision Engine (هفته 2–3)

### هدف
ساخت **قلب سیستم** — کاملاً مستقل از استراتژی و منبع داده.

### Engine
Engine فقط با `list[StrategySignal] + MarketContext + StateSnapshot` کار می‌کند.
تست با **MockSignalProvider** — نه استراتژی واقعی.

### Tasks

**Pipeline:**
- [x] `engine/market_filter.py`
- [x] `engine/aggregator.py`
- [x] `engine/risk_manager.py`
- [x] `engine/decision_engine.py` — orchestration + DecisionLog
- [x] `engine/final_signal_builder.py`

**Mock برای تست:**
- [x] `tests/mocks/mock_signals.py` — سیگنال‌های ثابت (جایگزین mock_providers)
- [x] `tests/mocks/fixtures.py` — context و StateSnapshot نمونه

**Tests (اجباری — قبل از Phase 2):**
- [x] consensus: 2 provider هم‌جهت → approved
- [x] conflict: BUY vs SELL → rejected
- [x] risk: drawdown exceeded → rejected
- [x] filter: low volatility → rejected
- [x] decision log کامل برای هر سناریو
- [x] max_signals_per_day, min_risk_reward, aggregation methods

### خروجی / معیار قبولی
- [x] `pytest tests/unit/engine/` — 100% pass
- [x] Engine بدون import از `strategies/` یا `data/` کار می‌کند
- [x] هر تصمیم `DecisionLog` دارد — حتی rejected

```
✓ Engine tested in isolation
✗ No strategies yet — by design
```

---

## Phase 2: Feature Builder (هفته 4)

### هدف
لایه **مشترک محاسبه ویژگی** — OHLCV → `FeatureSet` + `MarketContext`.

### چرا قبل از Runtime؟
Provider نباید اندیکاتور محاسبه کند. Runtime به Builder وابسته است.

### Tasks

- [x] `features/registry.py` — parse `config/features.yaml`
- [x] `features/builder.py` — `FeatureBuilder.build(df)` → FeatureSet + MarketContext
- [x] `features/indicators/` — RSI, EMA, MACD, ATR, Bollinger
- [x] `features/store.py` — `FeatureStore.put/get` + `feature_version`
- [x] `features/context_deriver.py` — trend, volatility, session از features
- [x] `config/features.yaml` — تعریف declarative اندیکاتورها

**Tests:**
- [x] snapshot: `df` ثابت → `FeatureSet` ثابت
- [x] `MarketContext` از features مشتق می‌شود — نه مستقل از Builder
- [x] افزودن اندیکاتور جدید = YAML + یک indicator class

### خروجی / معیار قبولی
- [x] `FeatureBuilder` بدون import از `providers/` یا `engine/`
- [x] RSI در دو Provider مختلف **یک بار** محاسبه می‌شود
- [x] `feature_set_version` در خروجی ثبت می‌شود

---

## Phase 3: Platform Runtime + Event Layer (هفته 5)

### هدف
یک **Runtime واحد** با pipeline کامل: data → **features** → providers → engine → events.

Runtime نباید DB، WebSocket یا Telegram را مستقیم صدا بزند. فقط `DomainEvent` منتشر می‌کند.

### Tasks

- [x] `runtime/platform_runtime.py` — شامل فراخوانی `feature_builder.build()`
- [x] `runtime/clocks.py` — `WallClock`, `SimulatedClock`
- [x] `state/store.py` — `StateStore`, `InMemoryStateStore`
- [x] `state/transitions.py` — `StateTransitionEvent`
- [x] `data/csv_provider.py`
- [x] `events/envelopes.py` — taxonomy: Market, Signal, Decision, Execution
- [x] `events/event_bus.py` — interface
- [x] `events/in_memory_bus.py` — MVP implementation
- [x] `events/handlers/logging_handler.py`
- [x] `events/handlers/event_log_handler.py` — نوشتن به `event_log` (اختیاری در MVP)
- [x] `tests/mocks/mock_providers.py` — ورودی: `FeatureSet` mock

**Integration test:**
- [x] Runtime + CSV + FeatureBuilder + FeatureStore + StateStore + MockProviders + Engine + InMemoryEventBus
- [x] هر cycle: `state_snapshot_id` در DecisionEvent
- [x] `DecisionApproved` / `DecisionRejected` با `event_time` ≠ `processing_time`

### خروجی / معیار قبولی
- [x] `run_cycle()` = fetch → features → store → snapshot state → providers → engine → publish events
- [x] گام feature build **همیشه** قبل از providers
- [x] Runtime هیچ import از Telegram/WebSocket/DB handler ندارد

مستندات: [event-model.md](../architecture/event-model.md), [feature-store.md](../architecture/feature-store.md)

---

## Phase 4: Validation Harness (هفته 6–7)

### هدف
بک‌تست به‌عنوان **ابزار سنجش Engine** — نه «برنامه بک‌تست استراتژی».

### تفاوت با رویکرد قدیم

| قدیم | جدید |
|------|------|
| BacktestRunner = simulate trades | ValidationHarness = iterate Runtime روی تاریخ |
| metrics = PnL استراتژی | metrics = کیفیت **تصمیمات** Engine + PnL |
| محصول جدا | adapter روی همان Runtime |

### Tasks

- [ ] `validation/harness.py` — iterate CSV؛ PnL از `ExecutionEngine` نه trade_simulator مستقیم
- [ ] `execution/simulated.py` — `SimulatedExecutionEngine` + `FillModel`
- [ ] `execution/risk_gate.py` — `ExecutionRiskGate` (pre-trade)
- [ ] `state/` — runtime cycle phases per [state-risk-contract.md](../architecture/state-risk-contract.md)
- [ ] `validation/metrics.py`:
  - **Engine metrics:** approval rate, rejection breakdown, provider contribution
  - **Outcome metrics:** win rate, Sharpe, max DD, profit factor
- [ ] `validation/report.py` — گزارش با تمرکز بر Decision quality
- [ ] DB models: `DecisionRecord`, `BacktestRun`, `SimulatedTrade`, `event_log`, `feature_sets`, `state_snapshots`
- [ ] Alembic migrations
- [ ] `scripts/run_validation.py` — CLI
- [ ] `replay/engine.py` — **strict replay** از `event_log` (MVP)
- [ ] `replay/timeline.py` — timeline per `correlation_id`

### معیارهای قبولی فاز

**Engine quality:**
- [ ] Decision log + `state_snapshot_id` برای 100% چرخه‌ها ذخیره می‌شود
- [ ] rejection breakdown گزارش می‌شود
- [ ] `event_log` chain کامل Market → Execution برای هر cycle

**Outcome (با Mock یا اولین Provider):**
- [ ] harness 1 ساله BTC/USDT < 60s
- [ ] metrics قابل reproduce

---

## Phase 5: Signal Providers (هفته 8)

### هدف
حالا — و فقط حالا — plug-in کردن استراتژی‌های واقعی.

### اصل
استراتژی **آخرین لایه** است. Engine و Runtime قبلاً تست شده‌اند.

### Tasks

- [ ] `providers/base.py` — `BaseSignalProvider` implements protocol
- [ ] `providers/registry.py` — register / discover
- [ ] `providers/ema_crossover.py` — تفسیر `features.flags["ema_cross_bullish"]`
- [ ] `providers/rsi_divergence.py` — تفسیر `features.indicators["rsi_14"]` + `ProviderRationale`
- [ ] `config/providers/*.yaml` — پارامترها
- [ ] Unit test هر provider — ورودی `FeatureSet` mock، **بدون** OHLCV
- [ ] Integration test: Runtime + real providers + validation harness

### خروجی / معیار قبولی
- [ ] افزودن provider سوم بدون تغییر Engine/Runtime
- [ ] `enabled: false` در config → provider skip می‌شود
- [ ] validation harness با providers واقعی اجرا می‌شود

```
Provider = plug-in
Engine = unchanged since Phase 1
```

---

## Phase 6: Observability — API & Dashboard (هفته 9–10)

### هدف
قابلیت مشاهده و کنترل **Engine** — نه فقط لیست استراتژی‌ها.

### اولویت صفحات (مهم ← کم‌اهمیت)

1. **Decision Monitor** — live feed + explainability + لینک replay
2. **Engine Config** — قوانین risk, aggregation, filter
3. **Forensic / Replay** — timeline و causal graph per decision
4. **Signals** — تصمیمات approved
5. **Validation Results** — نتایج harness
6. **Providers** — مدیریت استراتژی‌ها (secondary)

### Tasks

**API (FastAPI):**
- [ ] `GET /api/v1/decisions` — لیست تصمیمات (approved + rejected)
- [ ] `GET /api/v1/decisions/{id}` — decision log + explainability کامل
- [ ] `POST /api/v1/replay/cycle/{correlation_id}` — strict replay
- [ ] `GET /api/v1/replay/{job_id}/timeline`
- [ ] `GET /api/v1/engine/config` + `PATCH` — تنظیمات engine
- [ ] `GET /api/v1/engine/stats` — approval rate, rejection breakdown
- [ ] `GET /api/v1/signals` — فقط approved decisions
- [ ] `POST /api/v1/validation/run` — اجرای harness
- [ ] `GET /api/v1/providers` + `PATCH` — مدیریت providers
- [ ] `WS /ws/decisions` — real-time decision stream
- [ ] Auth (JWT)

**Frontend:**
- [ ] Layout + sidebar
- [ ] **صفحه Decision Monitor** (اولین صفحه — نه Overview کلاسیک)
- [ ] Engine Config page
- [ ] Signals list + detail (با decision log)
- [ ] Validation run + results
- [ ] Providers list (secondary)
- [ ] Dark theme

### خروجی / معیار قبولی
- [ ] هر rejection در UI با دلیل نمایش داده می‌شود
- [ ] validation از dashboard اجرا می‌شود
- [ ] تغییر engine config بدون redeploy provider

---

## Phase 7: Live Adapters (هفته 11)

### هدف
اتصال همان Runtime به بازار زنده — **فقط adapter عوض می‌شود**.

### Tasks

- [ ] `data/live_provider.py` (ccxt)
- [ ] `events/redis_bus.py` — Redis Pub/Sub یا Redis Streams
- [ ] `events/handlers/telegram_handler.py`
- [ ] `events/handlers/database_handler.py`
- [ ] `events/handlers/websocket_handler.py`
- [ ] `runtime/scheduler.py` — APScheduler
- [ ] `scripts/run_live.py` — `PlatformRuntime` + live adapters
- [ ] Paper mode: EventBus بدون `TelegramEventHandler`
- [ ] `GET/POST /api/v1/live/*` — status, start, stop, mode
- [ ] Frontend: Live status در Decision Monitor

### چک‌لیست یکسان‌سازی

| مورد | Validation | Live | یکسان؟ |
|------|------------|------|--------|
| `PlatformRuntime` | ✓ | ✓ | ✅ |
| `DecisionEngine` | ✓ | ✓ | ✅ |
| `SignalProvider` | ✓ | ✓ | ✅ |
| `EventBus` | InMemory | Redis | adapter |
| `MarketDataProvider` | CSV | ccxt | adapter |
| `EventHandlers` | Simulation+DB | DB+WS+Telegram | adapter |
| `Scheduler` | iterate | cron | adapter |

### خروجی / معیار قبولی
- [ ] Paper mode 1 هفته بدون خطا
- [ ] Telegram فقط `FinalSignal` از Engine — نه از provider
- [ ] Decision log لایو = همان schema بک‌تست

---

## Phase 8: Polish + Production Hardening (اختیاری)

- [ ] Replay re-execute + `DecisionDiff` — [replay-engine.md](../architecture/replay-engine.md)
- [ ] `governance/` — Experiment API + A/B comparison — [governance.md](../architecture/governance.md)
- [ ] `revision_id` / `experiment_id` در تمام `event_log`
- [ ] `LiveGovernanceGate` — live فقط با validation موفق revision
- [ ] Feature drift detection در replay
- [ ] Causal graph UI
- [ ] Analytics — rejection trends, provider contribution over time
- [ ] Walk-forward validation UI
- [ ] Engine A/B testing (دو config موازی)
- [ ] Export PDF/CSV
- [ ] Prometheus + Grafana
- [ ] E2E tests (Playwright)
- [ ] Production hardening

---

## Timeline

| فاز | مدت | Milestone |
|-----|-----|-----------|
| 0 | 1 هفته | Contracts + features.yaml |
| 1 | 2 هفته | Engine tested in isolation |
| 2 | 1 هفته | **Feature Builder** — FeatureSet + MarketContext |
| 3 | 1 هفته | Runtime with feature pipeline |
| 4 | 1–2 هفته | Validation harness |
| 5 | 1 هفته | Providers (interpret only) |
| 6 | 2 هفته | Dashboard — Decision Monitor |
| 7 | 1 هفته | Live adapters |
| 8 | 2+ هفته | Polish |

---

## Definition of Done — MVP

### Engine (غیرقابل مذاکره)
- [x] تصمیم approved/rejected با log کامل
- [x] تست unit بدون provider واقعی
- [x] config از YAML قابل تغییر

### Runtime
- [x] pipeline: data → features → store → state snapshot → providers → engine → events
- [x] side-effectها فقط در event handlers

### Infrastructure
- [ ] Event Model — chain کامل در `event_log`
- [x] StateStore — versioned snapshots + [state-risk-contract](../architecture/state-risk-contract.md)
- [ ] ExecutionEngine — Order/Fill chain — [execution-model](../architecture/execution-model.md)
- [x] FeatureStore — `feature_version` + `config_hash`
- [ ] Strict replay per `correlation_id`
- [ ] Explainability در API (`ProviderRationale`, `RiskVerdict`)
- [ ] Governance — `revision_id` در decisions و events

### Feature Builder
- [x] OHLCV → FeatureSet یکسان در Validation و Live (همان `DefaultFeatureBuilder` در Runtime)
- [ ] Provider بدون محاسبه اندیکاتور

### Validation
- [ ] harness با engine metrics
- [ ] outcome metrics (PnL) روی تصمیمات approved

### Providers
- [ ] حداقل 2 provider plug-in
- [ ] افزودن سوم بدون touch Engine

### Observability
- [ ] Decision Monitor با rejection reasons
- [ ] validation از UI

### Live
- [ ] paper mode پایدار
- [ ] telegram از engine path

---

## ریسک‌ها

| ریسک | Mitigation |
|------|------------|
| Engine زود پیچیده شود | Mock providers، تست قبل از provider واقعی |
| بک‌تست دوباره جدا شود | فقط ValidationHarness روی Runtime |
| Dashboard استراتژی‌محور شود | Decision Monitor = صفحه اول |
| Provider منطق indicator داشته باشد | فقط FeatureSet تفسیر کند |
| Overfitting provider | ارزیابی در سطح Engine outcome، walk-forward |

---

## خلاصه فلسفه

```
قدیم:  "چه استراتژی‌هایی بسازیم؟"
جدید:  "Engine چطور تصمیم می‌گیرد؟ Feature Builder بازار را چطور توصیف می‌کند؟
         Providerها بعداً فقط تفسیر می‌کنند."
```
