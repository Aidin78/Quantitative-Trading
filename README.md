# Quantitative Trading Signal Platform

پلتفرم تصمیم‌گیری معاملاتی — **Decision Engine** در مرکز، استراتژی‌ها به‌عنوان Signal Provider.

## ویژگی‌ها

- موتور تصمیم‌گیری (Decision Engine) — قلب سیستم
- Feature Builder برای محاسبه یکپارچه اندیکاتورها و `MarketContext`
- Event Layer برای انتشار Domain Eventها و جداسازی side-effectها
- State Management مرکزی — `PortfolioState`، `PositionState`، `RiskState` versioned
- Event Model رسمی — Market / Signal / Decision / Execution با lifecycle مشخص
- Feature Store برای ذخیره و نسخه‌بندی feature (کاهش drift بک‌تست/لایو)
- Replay Engine مستقل برای forensic debugging و causal analysis
- Time Semantics — `event_time`، `processing_time`، `decision_time`
- Explainability ساختاریافته — `ProviderRationale` و `RiskVerdict`
- Execution Model رسمی — OrderIntent → Fill → Position (جدا از Telegram)
- State–Risk Contract — مرز enforceable خواندن/نوشتن state
- Governance — Experiment Management، ConfigRevision، A/B testing
- Signal Providerهای plug-in (استراتژی‌ها)
- Validation harness برای سنجش کیفیت تصمیمات
- اتصال به بازار زنده با همان Runtime
- اعلان سیگنال از طریق Telegram
- داشبورد کامل برای تحلیل و کنترل

## مستندات

مستندات کامل فنی در پوشه [`docs/`](./docs/README.md):

- [معماری Engine-Centric](./docs/architecture/engine-centric.md)
- [Event Model](./docs/architecture/event-model.md)
- [State Management](./docs/architecture/state-management.md)
- [Replay Engine](./docs/architecture/replay-engine.md)
- [Feature Store](./docs/architecture/feature-store.md)
- [Time Semantics](./docs/architecture/time-semantics.md)
- [Explainability](./docs/architecture/explainability.md)
- [Execution Model](./docs/architecture/execution-model.md)
- [State–Risk Contract](./docs/architecture/state-risk-contract.md)
- [Governance](./docs/architecture/governance.md)
- [Backend Stack](./docs/backend/stack.md)
- [Frontend Stack](./docs/frontend/stack.md)
- [API](./docs/api/rest-api.md)
- [Deployment](./docs/deployment/docker.md)
- [Roadmap](./docs/development/roadmap.md)

## Stack

| لایه | تکنولوژی |
|------|----------|
| Frontend | Next.js 14, TypeScript, shadcn/ui |
| API | FastAPI, WebSocket |
| Decision Engine | Python — pipeline تصمیم |
| Feature Builder | pandas-ta / ta — اندیکاتورها |
| Platform Runtime | Python — چرخه اجرا |
| Event Layer | InMemoryEventBus (MVP)، Redis Pub/Sub/Streams (Live) |
| Event Model | Market / Signal / Decision / Execution + `event_log` |
| State Store | Portfolio / Position / Risk — versioned snapshots |
| Feature Store | PostgreSQL/TimescaleDB — feature versioned |
| Replay Engine | strict + re-execute replay، causal graph |
| Execution Engine | Order → Fill → Position؛ `FillModel` deterministic |
| Governance | Experiment، ConfigRevision، A/B comparison |
| Signal Providers | plug-in — تفسیر FeatureSet |
| Database | PostgreSQL + TimescaleDB |
| Cache | Redis |
| Notifications | Telegram Bot |

## شروع سریع

```bash
# Clone and setup
cp .env.example .env

# Infrastructure (postgres + redis)
docker compose up -d postgres redis

# Backend (development) — see backend/README.md for Windows Poetry setup
cd backend
# Windows: .\scripts\setup.ps1   OR   Git Bash: bash scripts/setup.sh
poetry run pytest
poetry run uvicorn src.main:app --reload

# Frontend (Phase 6 — placeholder)
cd frontend && npm install && npm run dev
```

## ساختار پروژه

```
quantitative-trading/
├── backend/          # Python — Core + API (Phase 0+)
├── frontend/         # Next.js — Dashboard (Phase 6)
├── config/           # تنظیمات مشترک (engine, features, providers)
├── docs/             # مستندات فنی
├── data/             # داده تاریخی CSV
├── docker-compose.yml
└── .env.example
```

## License

Private — All rights reserved.
