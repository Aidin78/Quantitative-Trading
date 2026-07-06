# Quantitative Trading Signal Platform — مستندات فنی

پلتفرم هوشمند تولید سیگنال‌های معاملاتی با Decision Engine یکپارچه، Feature Builder مشترک، Validation روی داده تاریخی و اتصال به بازار زنده.

## فهرست مستندات

| بخش | فایل | توضیح |
|-----|------|--------|
| **معماری** | [engine-centric.md](./architecture/engine-centric.md) | اصول معماری — Engine در مرکز |
| | [feature-builder.md](./architecture/feature-builder.md) | لایه Feature Builder — اندیکاتور و ویژگی |
| | [feature-store.md](./architecture/feature-store.md) | **Feature Store — ذخیره و نسخه‌بندی feature** |
| | [event-layer.md](./architecture/event-layer.md) | Event Layer — انتشار و fan-out |
| | [event-model.md](./architecture/event-model.md) | **Event Model — taxonomy و lifecycle رسمی** |
| | [state-management.md](./architecture/state-management.md) | **State Management — Portfolio/Risk/Position versioned** |
| | [replay-engine.md](./architecture/replay-engine.md) | **Replay Engine — forensic و بازپخش** |
| | [time-semantics.md](./architecture/time-semantics.md) | **Time Semantics — event/processing/decision time** |
| | [explainability.md](./architecture/explainability.md) | Explainability — Provider rationale و Risk verdict |
| | [execution-model.md](./architecture/execution-model.md) | **Execution Model — Order/Fill lifecycle رسمی** |
| | [state-risk-contract.md](./architecture/state-risk-contract.md) | **State–Risk Contract — مرز enforceable** |
| | [governance.md](./architecture/governance.md) | **Governance — Experiment Management و A/B** |
| | [overview.md](./architecture/overview.md) | معماری کلی سیستم |
| | [data-flow.md](./architecture/data-flow.md) | جریان داده در validation و لایو |
| **بک‌اند** | [stack.md](./backend/stack.md) | Stack و کتابخانه‌های Python |
| | [project-structure.md](./backend/project-structure.md) | ساختار پوشه‌ها |
| | [core-concepts.md](./backend/core-concepts.md) | مدل‌ها، استراتژی‌ها، موتور تصمیم‌گیری |
| | [backtesting.md](./backend/backtesting.md) | Validation Harness و معیارهای عملکرد |
| | [live-trading.md](./backend/live-trading.md) | فاز لایو و تلگرام |
| **فرانت‌اند** | [stack.md](./frontend/stack.md) | Stack و کتابخانه‌های Next.js |
| | [project-structure.md](./frontend/project-structure.md) | ساختار پوشه‌های فرانت |
| | [dashboard-pages.md](./frontend/dashboard-pages.md) | صفحات و جزئیات داشبورد |
| **API** | [rest-api.md](./api/rest-api.md) | REST Endpoints |
| | [websocket.md](./api/websocket.md) | رویدادهای WebSocket |
| **استقرار** | [docker.md](./deployment/docker.md) | Docker و محیط‌های اجرا |
| **توسعه** | [roadmap.md](./development/roadmap.md) | فازبندی پروژه |
| | [conventions.md](./development/conventions.md) | قراردادها و استانداردها |

## خلاصه Stack

```
┌─────────────────────────────────────────────────────────┐
│  Frontend: Next.js 14 + TypeScript + shadcn/ui          │
├─────────────────────────────────────────────────────────┤
│  API: FastAPI + WebSocket + JWT                         │
├─────────────────────────────────────────────────────────┤
│  Decision Engine          ← قلب — تصمیم نهایی           │
│  Feature Builder          ← ویژگی — اندیکاتور، context  │
│  Platform Runtime         ← چرخه اجرا                   │
│  Event Layer + Event Model ← taxonomy، store، replay      │
│  State Store              ← Portfolio / Risk / Position   │
│  Feature Store            ← feature versioned و replayable │
│  Replay Engine            ← forensic و causal analysis      │
│  Execution Engine         ← Order → Fill → Position         │
│  Governance               ← Experiment / ConfigRevision     │
│  Signal Providers         ← plug-in — تفسیر features    │
├─────────────────────────────────────────────────────────┤
│  Data: PostgreSQL/TimescaleDB + Redis + OHLCV adapters  │
├─────────────────────────────────────────────────────────┤
│  Output: Telegram Bot + Dashboard                       │
└─────────────────────────────────────────────────────────┘
```

## اصول طراحی

1. **Engine-Centric** — قلب سیستم Decision Engine است؛ استراتژی‌ها فقط Signal Provider.
2. **Feature Separation** — اندیکاتورها در Feature Builder؛ Provider فقط `FeatureSet` را تفسیر می‌کند.
3. **Contracts First** — قراردادها (`FeatureSet`, `Decision`, `StrategySignal`) قبل از implementation.
4. **یک Runtime، دو Adapter** — Validation و Live همان `PlatformRuntime`.
5. **Event-Driven Outputs** — Runtime فقط event منتشر می‌کند؛ DB/WS/Telegram handler هستند.
6. **Event Model رسمی** — Market → Signal → Decision → Execution با lifecycle مشخص.
7. **State مرکزی versioned** — `StateStore` برای determinism در validation و live.
8. **Feature Store** — feature ذخیره و نسخه‌بندی می‌شود؛ replay بدون drift.
9. **Time Semantics** — تفکیک `event_time`، `processing_time`، `decision_time`.
10. **Explainability** — `ProviderRationale` + `RiskVerdict` + `DecisionLog` structured.
11. **Replay Engine** — مستقل از Validation؛ forensic و causal analysis.
12. **Execution Model** — OrderIntent → Fill → Position؛ Telegram فقط notification.
13. **State–Risk Contract** — Risk read-only؛ StateStore تنها mutator.
14. **Governance** — Experiment، ConfigRevision، A/B comparison.
15. **مدیریت ریسک متمرکز** — RiskManager روی snapshot؛ pre-trade در ExecutionRiskGate.
16. **Validation قبل از Live** — بک‌تست ابزار سنجش Engine است.

## شروع سریع (پس از scaffold)

```bash
# بک‌اند
cd backend
poetry install
poetry run python scripts/run_validation.py

# فرانت‌اند
cd frontend
npm install
npm run dev

# Docker (کل سیستم)
docker compose up -d
```

## مخاطب مستندات

- **توسعه‌دهنده بک‌اند** → `backend/` + `api/`
- **توسعه‌دهنده فرانت** → `frontend/` + `api/`
- **DevOps** → `deployment/`
- **مدیر پروژه** → `development/roadmap.md`
