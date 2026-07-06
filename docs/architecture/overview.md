# معماری کلی سیستم

> **رویکرد:** Architecture-Driven — قلب سیستم `Decision Engine` است؛ استراتژی‌ها فقط `SignalProvider`.
> جزئیات: [engine-centric.md](./engine-centric.md)

## نمای کلی

سیستم از درون به بیرون حول Engine ساخته می‌شود:

```
┌──────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                         │
│         Dashboard (Decision Monitor)  │  Telegram Bot            │
├──────────────────────────────────────────────────────────────────┤
│                          API Layer                                │
│              FastAPI REST  │  WebSocket Hub  │  Auth             │
├──────────────────────────────────────────────────────────────────┤
│                       Event Layer + Event Model                   │
│   EventBus  │  event_log  │  Handlers  │  Replay Engine          │
├──────────────────────────────────────────────────────────────────┤
│              State Store + Feature Store + Clock                  │
│   PortfolioState │ RiskState │ FeatureSetRecord │ Time Semantics  │
├──────────────────────────────────────────────────────────────────┤
│                      Adapter Layer                                │
│   CSV/Live Data  │  Telegram/DB/WS Handlers  │  Scheduler        │
├──────────────────────────────────────────────────────────────────┤
│                      Platform Runtime                             │
│    data → features → providers → engine → events                 │
├──────────────────────────────────────────────────────────────────┤
│                    ★ Decision Engine ★                           │
│   MarketFilter → Aggregator → RiskManager → DecisionLog          │
├──────────────────────────────────────────────────────────────────┤
│                   Signal Providers (plug-in)                      │
│   Provider A  │  Provider B  │  Provider N  │  Registry          │
├──────────────────────────────────────────────────────────────────┤
│              ★ Feature Builder Layer ★                           │
│         OHLCV → FeatureSet + MarketContext                       │
├──────────────────────────────────────────────────────────────────┤
│              MarketDataProvider (OHLCV خام)                       │
├──────────────────────────────────────────────────────────────────┤
│                     Contracts (ثابت)                              │
│   FeatureSet │ StrategySignal │ Decision │ Protocols              │
└──────────────────────────────────────────────────────────────────┘
```

## اجزای اصلی

### 1. Data Layer (OHLCV خام)

| Provider | کاربرد | منبع |
|----------|--------|------|
| `CSVProvider` | validation | فایل‌های CSV |
| `LiveProvider` | لایو | ccxt / MT5 |

### 2. Feature Builder Layer

| جزء | مسئولیت |
|-----|----------|
| `FeatureBuilder` | OHLCV → `FeatureSet` + `MarketContext` |
| `FeatureRegistry` | اندیکاتورها از `config/features.yaml` |

جزئیات: [feature-builder.md](./feature-builder.md)

### 3. Signal Providers

استراتژی = **SignalProvider** — تفسیر `FeatureSet`، نه محاسبه اندیکاتور:
- ورودی: `FeatureSet` + `MarketContext`
- خروجی: `StrategySignal`
- از طریق `ProviderRegistry` ثبت می‌شود

### 4. Decision Engine (قلب سیستم)

تنها جایی که تصمیم نهایی گرفته می‌شود. `MarketContext` از Feature Builder — نه محاسبه مجدد.

مراحل پردازش:
1. **Market Filter** — بررسی شرایط کلی بازار (volatility، trend، session)
2. **Aggregator** — ترکیب نظر Providers (رأی‌گیری، وزن‌دهی)
3. **Risk Manager** — اعمال قوانین ریسک (drawdown، position size)
4. **Final Signal Builder** — ساخت `FinalSignal` در صورت تأیید
5. **DecisionLog** — ثبت شفاف هر مرحله (approved و rejected)

### 5. Platform Runtime

`PlatformRuntime`: fetch → **feature_builder.build()** → providers → engine → domain events.

### 6. Event Layer + Event Model

| جزء | مسئولیت |
|-----|----------|
| `EventBus` | انتشار eventها — [event-layer.md](./event-layer.md) |
| `EventEnvelope` | taxonomy رسمی — [event-model.md](./event-model.md) |
| `event_log` | ذخیره chain کامل برای replay |
| `ReplayEngine` | forensic و causal analysis — [replay-engine.md](./replay-engine.md) |

### 7. State Store

وضعیت مرکزی versioned — [state-management.md](./state-management.md):
- `PortfolioState`, `PositionState`, `RiskState`
- `StateSnapshot` قبل از هر تصمیم
- mutation فقط از طریق `StateTransitionEvent`

### 8. Execution Engine

تبدیل `FinalSignal` به Order → Fill → Position — [execution-model.md](./execution-model.md):
- `SimulatedExecutionEngine` در validation
- `ExecutionRiskGate` — pre-trade check روی snapshot جدید
- Telegram فقط مصرف‌کننده `SignalPublished`

### 9. State–Risk Contract

مرز enforceable — [state-risk-contract.md](./state-risk-contract.md):
- RiskManager: read-only روی snapshot
- StateStore: تنها mutator
- Runtime: state machine فاز cycle

### 10. Feature Store

ذخیره `FeatureSetRecord` با `feature_version` — [feature-store.md](./feature-store.md).

### 11. Time Semantics

`Clock` abstraction و تفکیک سه بعد زمان — [time-semantics.md](./time-semantics.md).

### 12. Governance

Experiment Management و ConfigRevision — [governance.md](./governance.md):
- `experiment_id` / `revision_id` در تمام eventها
- A/B comparison و lineage config

### 13. Adapter Layer

| Adapter | Validation | Live |
|---------|------------|------|
| `MarketDataProvider` | CSVProvider | LiveProvider |
| `EventBus` | InMemoryEventBus | Redis Pub/Sub یا Redis Streams |
| `EventHandlers` | Execution (simulated) + DB | DB + WS + Telegram |

### 14. API Layer

FastAPI — مشاهده‌پذیری Engine و تصمیمات:
- REST: `/decisions`, `/engine/config`, `/validation`
- WebSocket: `/ws/decisions`
- JWT برای auth

### 15. Presentation Layer

- **Dashboard** — Decision Monitor به‌عنوان صفحه اصلی
- **Telegram** — فقط `FinalSignal` از مسیر Engine

## دو حالت اجرا — فقط Adapter عوض می‌شود

| حالت | MarketDataProvider | EventBus | EventHandlers | زمان‌بندی |
|------|-------------------|----------|---------------|-----------|
| **Validation** | CSV | InMemory | Simulation + DB + progress | iterate تاریخ |
| **Live** | Live API (ccxt) | Redis | DB + WS + Telegram | Scheduler |

**نکته حیاتی:** `PlatformRuntime` + `DecisionEngine` در هر دو حالت **همان کد** هستند. Validation (بک‌تست) ابزار سنجش Engine است — نه محصول جدا.

## Monorepo Structure

```
quantitative-trading/
├── backend/                 # Python — Core + API
│   ├── src/
│   ├── tests/
│   ├── scripts/
│   └── pyproject.toml
├── frontend/                # Next.js — Dashboard
│   ├── app/
│   ├── components/
│   └── package.json
├── docs/                    # این مستندات
├── data/
│   └── historical/          # CSV فایل‌ها
├── config/                  # تنظیمات مشترک
├── docker-compose.yml
└── README.md
```

## ارتباط سرویس‌ها

```
                    ┌─────────────┐
                    │  Frontend   │
                    │  :3000      │
                    └──────┬──────┘
                           │ HTTP / WS
                    ┌──────▼──────┐
                    │  FastAPI    │
                    │  :8000      │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │  PostgreSQL │ │    Redis    │ │  Telegram   │
    │  :5432      │ │  :6379      │ │  API        │
    └─────────────┘ └─────────────┘ └─────────────┘
```

## الگوهای طراحی استفاده‌شده

| الگو | محل استفاده |
|------|-------------|
| **Protocol** | `SignalProvider`, `MarketDataProvider`, `EventBus`, `EventHandler` |
| **Pipeline** | Decision Engine — filter → aggregate → risk → log |
| **Adapter** | CSV/Live data، Telegram/DB sinks |
| **Registry** | `ProviderRegistry` — plug-in providers |
| **Event Bus** | `DomainEvent` fan-out به handlerها |
| **Observer** | WebSocket handler — publish event به dashboard |
| **Repository** | DB — decisions, validation runs, trades |

## ملاحظات امنیتی

- API keys و bot token فقط در `.env` — هرگز در git
- JWT با expiry کوتاه برای dashboard
- Rate limiting روی API endpoints
- Telegram فقط send — بدون دریافت دستور از کاربران ناشناس (در فاز اول)
