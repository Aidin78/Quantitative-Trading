# Backend Stack

## زبان و Runtime

| مورد | انتخاب | نسخه |
|------|--------|------|
| زبان | Python | 3.11+ |
| Package Manager | Poetry یا uv | latest |
| Type Checking | mypy (optional) | — |

## کتابخانه‌های اصلی

### داده و محاسبات

| کتابخانه | کاربرد |
|----------|--------|
| **pandas** | DataFrame، OHLCV، windowing |
| **numpy** | محاسبات عددی |
| **polars** | (اختیاری) داده حجیم — جایگزین سریع‌تر pandas |

### Feature Builder و اندیکاتورها

| کتابخانه | کاربرد |
|----------|--------|
| **ta** یا **pandas-ta** | فقط در `features/` برای RSI, MACD, EMA, Bollinger, ATR |

**قاعده معماری:** هیچ `SignalProvider` نباید مستقیماً `ta`، `pandas-ta` یا محاسبات اندیکاتور را import کند. Provider فقط `FeatureSet` را تفسیر می‌کند.

### Validation Harness

| گزینه | مزایا | معایب |
|-------|-------|-------|
| **Validation Harness سفارشی** | روی همان `PlatformRuntime` اجرا می‌شود و کیفیت Decision را می‌سنجد | توسعه بیشتر |
| **VectorBT** | سرعت بالا، vectorized | منحنی یادگیری |
| **Backtrader** | انعطاف، community | کندتر از VectorBT |

**پیشنهاد:** `ValidationHarness` سفارشی که `PlatformRuntime` را روی تاریخ iterate کند. این روش جلوی جدا شدن منطق validation و live را می‌گیرد.

### API

| کتابخانه | کاربرد |
|----------|--------|
| **FastAPI** | REST + WebSocket + OpenAPI |
| **uvicorn** | ASGI server |
| **pydantic** | validation، settings، schemas |
| **python-jose** | JWT |
| **passlib** | hash password |

### دیتابیس

| کتابخانه | کاربرد |
|----------|--------|
| **SQLAlchemy 2.0** | ORM |
| **alembic** | migrations |
| **asyncpg** | PostgreSQL async driver |
| **psycopg2** | sync fallback |

### کش و صف

| کتابخانه | کاربرد |
|----------|--------|
| **redis** | pub/sub، cache |
| **celery** (اختیاری) | background jobs — بک‌تست سنگین |

### بازار زنده

| بازار | کتابخانه |
|-------|----------|
| کریپتو | **ccxt** |
| فارکس | **MetaTrader5** |
| سهام ایران | API کارگزاری / tse-client |

### زمان‌بندی

| کتابخانه | کاربرد |
|----------|--------|
| **APScheduler** | cron-like برای live runner |
| **celery beat** | اگر Celery استفاده شود |

### اعلان‌ها

| کتابخانه | کاربرد |
|----------|--------|
| **python-telegram-bot** | ارسال سیگنال به کانال |

### لاگ و مانیتورینگ

| کتابخانه | کاربرد |
|----------|--------|
| **structlog** یا **loguru** | structured logging |
| **prometheus-client** | metrics (فاز بعد) |

### تست

| کتابخانه | کاربرد |
|----------|--------|
| **pytest** | unit + integration |
| **pytest-asyncio** | تست async |
| **httpx** | تست FastAPI |
| **factory-boy** | fixtures |

### ابزارهای توسعه

| ابزار | کاربرد |
|-------|--------|
| **ruff** | lint + format |
| **pre-commit** | hooks |
| **python-dotenv** | env vars |

## pyproject.toml (نمونه وابستگی‌ها)

```toml
[tool.poetry.dependencies]
python = "^3.11"
pandas = "^2.2"
numpy = "^1.26"
ta = "^0.11"
fastapi = "^0.115"
uvicorn = { extras = ["standard"], version = "^0.32" }
pydantic = "^2.9"
pydantic-settings = "^2.6"
sqlalchemy = "^2.0"
alembic = "^1.14"
asyncpg = "^0.30"
redis = "^5.2"
ccxt = "^4.4"
apscheduler = "^3.10"
python-telegram-bot = "^21.7"
structlog = "^24.4"
python-jose = { extras = ["cryptography"], version = "^3.3" }
passlib = { extras = ["bcrypt"], version = "^1.7" }
python-dotenv = "^1.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3"
pytest-asyncio = "^0.24"
httpx = "^0.28"
ruff = "^0.8"
```

## ساختار لایه‌های بک‌اند

```
backend/src/
├── api/              # FastAPI routes, deps, websocket
├── core/             # models, enums, exceptions
├── data/             # MarketDataProvider adapters
├── features/         # FeatureBuilder, indicators, context derivation
├── providers/        # SignalProviders (استراتژی‌های plug-in)
├── engine/           # DecisionEngine
├── runtime/          # PlatformRuntime
├── validation/       # ValidationHarness, simulated trades, metrics
├── sinks/            # logging, database, telegram, websocket sinks
├── db/               # sqlalchemy models, repositories
└── config/           # settings loader
```

## انتخاب بازار هدف

| بازار | CSV بک‌تست | Live API | نکته |
|-------|------------|----------|------|
| **کریپتو** | Export از ccxt یا TradingView | Binance/Bybit WebSocket | شروع سریع، API رایگان |
| **فارکس** | MetaTrader history | MT5 Python API | نیاز به terminal |
| **سهام ایران** | فایل دستی | API کارگزاری | محدودیت API |

**پیشنهاد فاز ۱:** کریپتو (BTC/USDT, ETH/USDT) — دسترسی آسان به داده و API.

## Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/trading

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNEL_ID=

# Exchange (Live)
EXCHANGE_API_KEY=
EXCHANGE_API_SECRET=

# Auth
JWT_SECRET=
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# App
ENV=development
LOG_LEVEL=INFO
```
