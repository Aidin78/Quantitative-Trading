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
│    data → features → providers → engine → sink                   │
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

`PlatformRuntime`: fetch → **feature_builder.build()** → providers → engine → sink.

### 6. Adapter Layer

| Adapter | Validation | Live |
|---------|------------|------|
| `MarketDataProvider` | CSVProvider | LiveProvider |
| `DecisionSink` | SimulatedTradeSink | Telegram + DB + WS |

### 7. API Layer

FastAPI — مشاهده‌پذیری Engine و تصمیمات:
- REST: `/decisions`, `/engine/config`, `/validation`
- WebSocket: `/ws/decisions`
- JWT برای auth

### 8. Presentation Layer

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
