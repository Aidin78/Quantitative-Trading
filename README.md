# Quantitative Trading Signal Platform

پلتفرم تصمیم‌گیری معاملاتی — **Decision Engine** در مرکز، استراتژی‌ها به‌عنوان Signal Provider.

## ویژگی‌ها

- موتور تصمیم‌گیری (Decision Engine) — قلب سیستم
- Signal Providerهای plug-in (استراتژی‌ها)
- Validation harness برای سنجش کیفیت تصمیمات
- اتصال به بازار زنده با همان Runtime
- اعلان سیگنال از طریق Telegram
- داشبورد کامل برای تحلیل و کنترل

## مستندات

مستندات کامل فنی در پوشه [`docs/`](./docs/README.md):

- [معماری Engine-Centric](./docs/architecture/engine-centric.md)
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
| Core | Python 3.11, pandas, Decision Engine |
| Database | PostgreSQL + TimescaleDB |
| Cache | Redis |
| Notifications | Telegram Bot |

## شروع سریع

```bash
# Clone and setup
cp .env.example .env

# Run with Docker
docker compose up -d

# Backend (development)
cd backend && poetry install
poetry run uvicorn src.main:app --reload

# Frontend (development)
cd frontend && npm install && npm run dev
```

## ساختار پروژه

```
quantitative-trading/
├── backend/          # Python — Core + API
├── frontend/         # Next.js — Dashboard
├── docs/             # مستندات فنی
├── config/           # تنظیمات
├── data/             # داده تاریخی CSV
└── docker-compose.yml
```

## License

Private — All rights reserved.
