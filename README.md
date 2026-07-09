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
- Governance — Experiment Management، ConfigRevision، replay re-execute
- Analytics — روند تصمیمات، مشارکت provider، heatmap زمانی
- Observability — Prometheus `/metrics`، Grafana dashboard (اختیاری)
- Export CSV — decisions و validation results
- Walk-forward validation — پنجره‌های rolling
- Feature drift detection در replay re-execute
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
| Observability | Prometheus + Grafana (profile `observability`) |

**Phase فعلی:** `8-production-mvp` — [`/health`](http://localhost:8000/health)

## شروع سریع

### روش پیشنهادی — همه‌چیز با Docker

```bash
cp .env.example .env
docker compose up -d --build
```

داشبورد: [http://localhost:3000](http://localhost:3000) · API: [http://localhost:8000](http://localhost:8000)

```bash
docker compose logs -f backend frontend   # لاگ‌ها
docker compose down                       # توقف
```

> اگر `npm run dev` لوکال دارید، اول آن را متوقف کنید (پورت 3000 مشترک است).

### روش توسعه — backend/frontend جدا (اختیاری)

```bash
# Infrastructure (postgres + redis)
docker compose up -d postgres redis

# Backend (development) — see backend/README.md for Windows Poetry setup
cd backend
# Windows: .\scripts\setup.ps1   OR   Git Bash: bash scripts/setup.sh
poetry install
poetry run pytest
poetry run uvicorn src.main:app --reload --port 8000

# Frontend dashboard
cd ../frontend
npm install
npm run dev

# E2E smoke tests (starts backend + frontend automatically)
npm run test:e2e

# Observability stack (Prometheus + Grafana)
docker compose --profile observability up -d
# Prometheus: http://localhost:9090  |  Grafana: http://localhost:3001 (admin/admin)
```

داشبورد روی [http://localhost:3000](http://localhost:3000) و API روی [http://localhost:8000](http://localhost:8000) در دسترس است.

### متغیرهای محیطی مهم

| متغیر | پیش‌فرض | توضیح |
|--------|---------|--------|
| `AUTH_REQUIRED` | `false` | در dev بدون لاگین |
| `CORS_ORIGINS` | `http://localhost:3000` | origin فرانت‌اند |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | آدرس API برای فرانت‌اند |

### اولین استفاده از داشبورد

1. Backend و Frontend را اجرا کنید.
2. به صفحه **Validation** بروید و یک harness اجرا کنید.
3. نتایج در **Decision Monitor**، **Analytics**، **Signals** و **Replay** نمایش داده می‌شوند.
4. از **Export CSV** در Decision Monitor یا Validation برای دانلود داده استفاده کنید.

تنظیمات پیش‌فرض symbol و timeframe در [`config/settings.yaml`](./config/settings.yaml) تعریف شده‌اند.

### CI

GitHub Actions workflow [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) روی هر push/PR به `main`:

- `poetry run pytest` (backend)
- `npm run lint` + `npm run build` (frontend)
- Playwright smoke tests (E2E)

## ساختار پروژه

```
quantitative-trading/
├── backend/          # Python — Core + API (Phase 0+)
├── frontend/         # Next.js 14 — Decision Monitor dashboard
├── config/           # تنظیمات مشترک (engine, features, providers)
├── docs/             # مستندات فنی
├── data/             # داده تاریخی CSV
├── docker-compose.yml
└── .env.example
```

## License

Private — All rights reserved.
