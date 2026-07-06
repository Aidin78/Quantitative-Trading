# Quantitative Trading Signal Platform — مستندات فنی

پلتفرم هوشمند تولید سیگنال‌های معاملاتی با موتور تصمیم‌گیری یکپارچه، بک‌تست روی داده تاریخی و اتصال به بازار زنده.

## فهرست مستندات

| بخش | فایل | توضیح |
|-----|------|--------|
| **معماری** | [engine-centric.md](./architecture/engine-centric.md) | **اصول معماری — Engine در مرکز** |
| | [overview.md](./architecture/overview.md) | معماری کلی سیستم |
| | [data-flow.md](./architecture/data-flow.md) | جریان داده در validation و لایو |
| **بک‌اند** | [stack.md](./backend/stack.md) | Stack و کتابخانه‌های Python |
| | [project-structure.md](./backend/project-structure.md) | ساختار پوشه‌ها |
| | [core-concepts.md](./backend/core-concepts.md) | مدل‌ها، استراتژی‌ها، موتور تصمیم‌گیری |
| | [backtesting.md](./backend/backtesting.md) | فاز بک‌تست و معیارهای عملکرد |
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
│  Core: Decision Engine + Runtime + Signal Providers     │
├─────────────────────────────────────────────────────────┤
│  Data: PostgreSQL/TimescaleDB + Redis                   │
├─────────────────────────────────────────────────────────┤
│  Output: Telegram Bot + Dashboard                       │
└─────────────────────────────────────────────────────────┘
```

## اصول طراحی

1. **Engine-Centric** — قلب سیستم Decision Engine است؛ استراتژی‌ها فقط Signal Provider.
2. **Contracts First** — قراردادها قبل از implementation تعریف می‌شوند.
3. **یک Runtime، دو Adapter** — Validation و Live همان `PlatformRuntime`؛ فقط data/sink عوض می‌شود.
4. **مدیریت ریسک متمرکز** — قوانین ریسک فقط در Engine.
5. **شفافیت تصمیم** — هر Decision (approved + rejected) با `DecisionLog` ثبت می‌شود.
6. **Validation قبل از Live** — بک‌تست ابزار سنجش کیفیت Engine است، نه محصول جدا.

## شروع سریع (پس از scaffold)

```bash
# بک‌اند
cd backend
poetry install
poetry run python scripts/run_backtest.py

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
