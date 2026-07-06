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
│                      Adapter Layer                                │
│   CSV/Live Data  │  Telegram/DB/WS Sinks  │  Scheduler           │
├──────────────────────────────────────────────────────────────────┤
│                      Platform Runtime                             │
│         data → providers → engine → sink (یک چرخه واحد)          │
├──────────────────────────────────────────────────────────────────┤
│                    ★ Decision Engine ★                           │
│   MarketFilter → Aggregator → RiskManager → DecisionLog          │
├──────────────────────────────────────────────────────────────────┤
│                   Signal Providers (plug-in)                      │
│   Provider A  │  Provider B  │  Provider N  │  Registry          │
├──────────────────────────────────────────────────────────────────┤
│                     Contracts (ثابت)                                │
│   StrategySignal │ Decision │ MarketContext │ Protocols            │
└──────────────────────────────────────────────────────────────────┘
```

## اجزای اصلی

### 1. Data Layer

مسئول تأمین داده OHLCV و context بازار. دو پیاده‌سازی دارد:

| Provider | کاربرد | منبع |
|----------|--------|------|
| `CSVProvider` | بک‌تست | فایل‌های CSV تاریخی |
| `LiveProvider` | لایو | ccxt / MetaTrader5 / API کارگزاری |

هر دو از interface یکسان `MarketDataProvider` پیروی می‌کنند.

### 2. Signal Providers (استراتژی‌ها)

استراتژی = **SignalProvider** — منبع نظر تحلیلی، نه تصمیم‌گیر نهایی:
- فقط `StrategySignal` برمی‌گرداند
- هیچ دسترسی به Telegram، DB، یا Risk ندارد
- از طریق `ProviderRegistry` ثبت می‌شود
- افزودن provider جدید = plug-in — بدون تغییر Engine

### 3. Decision Engine (قلب سیستم)

تنها جایی که تصمیم نهایی گرفته می‌شود. ورودی: `list[StrategySignal]` + `MarketContext` + `PortfolioState`. خروجی: `Decision` (approved | rejected).

مراحل پردازش:
1. **Market Filter** — بررسی شرایط کلی بازار (volatility، trend، session)
2. **Aggregator** — ترکیب نظر Providers (رأی‌گیری، وزن‌دهی)
3. **Risk Manager** — اعمال قوانین ریسک (drawdown، position size)
4. **Final Signal Builder** — ساخت `FinalSignal` در صورت تأیید
5. **DecisionLog** — ثبت شفاف هر مرحله (approved و rejected)

### 4. Platform Runtime

`PlatformRuntime` Engine را در یک چرخه اجرا می‌کند: fetch → providers → engine → sink.

### 5. Adapter Layer

| Adapter | Validation | Live |
|---------|------------|------|
| `MarketDataProvider` | CSVProvider | LiveProvider |
| `DecisionSink` | SimulatedTradeSink | Telegram + DB + WS |

### 6. API Layer

FastAPI — مشاهده‌پذیری Engine و تصمیمات:
- REST: `/decisions`, `/engine/config`, `/validation`
- WebSocket: `/ws/decisions`
- JWT برای auth

### 7. Presentation Layer

- **Dashboard** — Decision Monitor به‌عنوان صفحه اصلی
- **Telegram** — فقط `FinalSignal` از مسیر Engine

## دو حالت اجرا — فقط Adapter عوض می‌شود

| حالت | MarketDataProvider | DecisionSink | زمان‌بندی |
|------|-------------------|--------------|-----------|
| **Validation** | CSV | SimulatedTradeSink | iterate تاریخ |
| **Live** | Live API (ccxt) | Telegram + DB + WS | Scheduler |

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
| **Protocol** | `SignalProvider`, `MarketDataProvider`, `DecisionSink` |
| **Pipeline** | Decision Engine — filter → aggregate → risk → log |
| **Adapter** | CSV/Live data، Telegram/DB sinks |
| **Registry** | `ProviderRegistry` — plug-in providers |
| **Composite** | `CompositeSink` — چند مقصد برای یک decision |
| **Observer** | WebSocket — publish decision به dashboard |
| **Repository** | DB — decisions, validation runs, trades |

## ملاحظات امنیتی

- API keys و bot token فقط در `.env` — هرگز در git
- JWT با expiry کوتاه برای dashboard
- Rate limiting روی API endpoints
- Telegram فقط send — بدون دریافت دستور از کاربران ناشناس (در فاز اول)
