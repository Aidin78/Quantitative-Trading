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
Contracts   →    Decision Engine  →   Feature Builder  →   Platform Runtime
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
- [ ] Monorepo: `backend/`, `frontend/`, `docs/`
- [ ] Poetry, Docker Compose (postgres, redis)
- [ ] ruff, pre-commit, ESLint, Prettier

**Contracts (`src/core/contracts/`):**
- [ ] `signal.py` — `StrategySignal`, `FinalSignal`
- [ ] `decision.py` — `Decision`, `DecisionResult`, `RejectionReason`, `DecisionLog`
- [ ] `features.py` — `FeatureSet`, `FeatureBuilder` protocol
- [ ] `context.py` — `MarketContext`, `PortfolioState`
- [ ] `provider.py` — `SignalProvider` protocol (`analyze(features, context)`)
- [ ] `data.py` — `MarketDataProvider` protocol
- [ ] `sink.py` — `DecisionSink` protocol

**Config schema:**
- [ ] `config/engine.yaml` — قوانین aggregation, filter, risk
- [ ] `config/features.yaml` — اندیکاتورها و flags (declarative)
- [ ] Pydantic settings loader

### خروجی / معیار قبولی
- [ ] Contracts import می‌شوند بدون وابستگی به implementation
- [ ] `Decision` می‌تواند `approved(FinalSignal)` یا `rejected(reason)` باشد
- [ ] هیچ فایلی در `strategies/` وجود ندارد — عمداً

---

## Phase 1: Decision Engine (هفته 2–3)

### هدف
ساخت **قلب سیستم** — کاملاً مستقل از استراتژی و منبع داده.

### اصل
Engine فقط با `list[StrategySignal] + MarketContext + PortfolioState` کار می‌کند.
تست با **MockSignalProvider** — نه استراتژی واقعی.

### Tasks

**Pipeline:**
- [ ] `engine/market_filter.py`
- [ ] `engine/aggregator.py`
- [ ] `engine/risk_manager.py`
- [ ] `engine/decision_engine.py` — orchestration
- [ ] `engine/decision_log.py` — ثبت هر مرحله

**Mock برای تست:**
- [ ] `tests/mocks/mock_providers.py` — providerهای با خروجی ثابت
- [ ] `tests/mocks/fixtures.py` — context و portfolio نمونه

**Tests (اجباری — قبل از Phase 2):**
- [ ] consensus: 2 provider هم‌جهت → approved
- [ ] conflict: BUY vs SELL → rejected
- [ ] risk: drawdown exceeded → rejected
- [ ] filter: low volatility → rejected
- [ ] decision log کامل برای هر سناریو

### خروجی / معیار قبولی
- [ ] `pytest tests/unit/engine/` — 100% pass
- [ ] Engine بدون import از `strategies/` یا `data/` کار می‌کند
- [ ] هر تصمیم `DecisionLog` دارد — حتی rejected

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

- [ ] `features/registry.py` — parse `config/features.yaml`
- [ ] `features/builder.py` — `FeatureBuilder.build(df)` → FeatureSet + MarketContext
- [ ] `features/indicators/` — RSI, EMA, MACD, ATR, Bollinger
- [ ] `features/context_deriver.py` — trend, volatility, session از features
- [ ] `config/features.yaml` — تعریف declarative اندیکاتورها

**Tests:**
- [ ] snapshot: `df` ثابت → `FeatureSet` ثابت
- [ ] `MarketContext` از features مشتق می‌شود — نه مستقل از Builder
- [ ] افزودن اندیکاتور جدید = YAML + یک indicator class

### خروجی / معیار قبولی
- [ ] `FeatureBuilder` بدون import از `providers/` یا `engine/`
- [ ] RSI در دو Provider مختلف **یک بار** محاسبه می‌شود
- [ ] `feature_set_version` در خروجی ثبت می‌شود

---

## Phase 3: Platform Runtime (هفته 5)

### هدف
یک **Runtime واحد** با pipeline کامل: data → **features** → providers → engine → sink.

### Tasks

- [ ] `runtime/platform_runtime.py` — شامل فراخوانی `feature_builder.build()`
- [ ] `runtime/portfolio_tracker.py`
- [ ] `data/csv_provider.py`
- [ ] `sinks/logging_sink.py`
- [ ] `tests/mocks/mock_providers.py` — ورودی: `FeatureSet` mock

**Integration test:**
- [ ] Runtime + CSV + FeatureBuilder + MockProviders + Engine + LoggingSink

### خروجی / معیار قبولی
- [ ] `run_cycle()` = fetch → build features → providers → engine → sink
- [ ] گام feature build **همیشه** قبل از providers

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

- [ ] `validation/harness.py` — iterate CSV، صدا زدن `PlatformRuntime.run_cycle()`
- [ ] `validation/trade_simulator.py` — شبیه‌سازی معامله **بعد از** تصمیم approved
- [ ] `sinks/simulated_trade_sink.py` — ثبت معاملات شبیه‌سازی‌شده
- [ ] `validation/metrics.py`:
  - **Engine metrics:** approval rate, rejection breakdown, provider contribution
  - **Outcome metrics:** win rate, Sharpe, max DD, profit factor
- [ ] `validation/report.py` — گزارش با تمرکز بر Decision quality
- [ ] DB models: `DecisionRecord`, `BacktestRun`, `SimulatedTrade`
- [ ] Alembic migrations
- [ ] `scripts/run_validation.py` — CLI

### معیارهای قبولی فاز

**Engine quality:**
- [ ] Decision log برای 100% چرخه‌ها ذخیره می‌شود
- [ ] rejection breakdown گزارش می‌شود

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
- [ ] `providers/rsi_divergence.py` — تفسیر `features.indicators["rsi_14"]`
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

1. **Decision Monitor** — live feed تصمیمات + rejection reasons
2. **Engine Config** — قوانین risk, aggregation, filter
3. **Signals** — تصمیمات approved
4. **Validation Results** — نتایج harness
5. **Providers** — مدیریت استراتژی‌ها (secondary)

### Tasks

**API (FastAPI):**
- [ ] `GET /api/v1/decisions` — لیست تصمیمات (approved + rejected)
- [ ] `GET /api/v1/decisions/{id}` — decision log کامل
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
- [ ] `sinks/telegram_sink.py`
- [ ] `sinks/database_sink.py`
- [ ] `sinks/websocket_sink.py` — Redis pub/sub
- [ ] `runtime/scheduler.py` — APScheduler
- [ ] `scripts/run_live.py` — `PlatformRuntime` + live adapters
- [ ] Paper mode: `CompositeSink(LoggingSink)` بدون Telegram
- [ ] `GET/POST /api/v1/live/*` — status, start, stop, mode
- [ ] Frontend: Live status در Decision Monitor

### چک‌لیست یکسان‌سازی

| مورد | Validation | Live | یکسان؟ |
|------|------------|------|--------|
| `PlatformRuntime` | ✓ | ✓ | ✅ |
| `DecisionEngine` | ✓ | ✓ | ✅ |
| `SignalProvider` | ✓ | ✓ | ✅ |
| `MarketDataProvider` | CSV | ccxt | adapter |
| `DecisionSink` | Simulated | Telegram+DB+WS | adapter |
| `Scheduler` | iterate | cron | adapter |

### خروجی / معیار قبولی
- [ ] Paper mode 1 هفته بدون خطا
- [ ] Telegram فقط `FinalSignal` از Engine — نه از provider
- [ ] Decision log لایو = همان schema بک‌تست

---

## Phase 8: Polish (اختیاری)

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
- [ ] تصمیم approved/rejected با log کامل
- [ ] تست unit بدون provider واقعی
- [ ] config از YAML قابل تغییر

### Runtime
- [ ] pipeline: data → features → providers → engine → sink

### Feature Builder
- [ ] OHLCV → FeatureSet یکسان در Validation و Live
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
