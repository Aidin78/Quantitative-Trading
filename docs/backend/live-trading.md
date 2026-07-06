# معاملات زنده (Live Trading)

## هدف

اجرای همان `PlatformRuntime` روی داده real-time و ارسال فقط تصمیم‌های `approved` از طریق Telegram و Dashboard.

## پیش‌شرط

- Validation با معیارهای قبولی انجام شده
- پارامترها و قوانین ریسک finalize شده
- **هیچ تغییری در Feature Builder، Runtime یا Engine** نسبت به Validation

## معماری لایو

```
APScheduler
    │
    ├── Job: BTC/USDT 1h  (هر ساعت)
    ├── Job: BTC/USDT 4h  (هر 4 ساعت)
    └── Job: ETH/USDT 1h
            │
            ▼
    PlatformRuntime.run_cycle(symbol, timeframe)
            │
            ▼
    LiveProvider.get_latest()
            │
            ▼
    FeatureBuilder → Providers → DecisionEngine → Decision
            │
    ┌───────┼───────┐
    ▼       ▼       ▼
   DB    Redis   Telegram
            │
            ▼
       WebSocket → Dashboard
```

## Live Runtime

```python
class LiveRuntime:
    def __init__(
        self,
        data_provider: LiveProvider,
        feature_builder: FeatureBuilder,
        providers: list[SignalProvider],
        engine: DecisionEngine,
        sink: CompositeSink,
    ): ...

    async def execute(self, symbol: str, timeframe: str) -> None:
        df = await self.data_provider.get_latest(symbol, timeframe)
        features, context = self.feature_builder.build(df, symbol, timeframe)
        portfolio = await self._load_portfolio_state()

        signals = [p.analyze(features, context) for p in self.providers if p.enabled]
        decision = self.engine.process(signals, context, portfolio)

        await self.sink.handle(decision)
```

## LiveProvider (ccxt)

```python
class LiveProvider(MarketDataProvider):
    def __init__(self, exchange_id: str = "binance"):
        self.exchange = ccxt.binance({...})

    async def get_latest(self, symbol: str, timeframe: str,
                         limit: int = 200) -> pd.DataFrame:
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return self._to_dataframe(ohlcv)
```

## Scheduler

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# هر ساعت در دقیقه 1 (بعد از بسته شدن کندل)
scheduler.add_job(
    live_runner.execute,
    "cron",
    minute=1,
    args=["BTC/USDT", "1h"],
)

scheduler.add_job(
    live_runner.execute,
    "cron",
    hour="*/4",
    minute=1,
    args=["BTC/USDT", "4h"],
)
```

## Telegram Notifier

### فرمت پیام

```
🟢 BUY | BTC/USDT | 1H
━━━━━━━━━━━━━━━━━━
📍 Entry: 67,250
🛑 SL: 66,800 (-0.67%)
🎯 TP: 68,500 (+1.86%)
📊 R:R = 1:2.8

💪 Confidence: 78%
✅ Providers: EMA Cross, RSI Div
📈 Market: Trending ↑ | Vol: Normal

⏰ 2026-07-06 10:30 UTC
⚠️ Not financial advice
```

### پیاده‌سازی

```python
class TelegramNotifier:
    def __init__(self, bot_token: str, channel_id: str):
        self.bot = Bot(token=bot_token)
        self.channel_id = channel_id

    async def send(self, signal: FinalSignal) -> None:
        message = self._format_signal(signal)
        await self.bot.send_message(
            chat_id=self.channel_id,
            text=message,
            parse_mode="HTML",
        )
```

## حالت‌های اجرا

| حالت | توضیح |
|------|--------|
| **paper** | Decision تولید و لاگ — بدون Telegram |
| **live** | DB + WebSocket + Telegram فقط برای approved |
| **paused** | Scheduler متوقف — فقط مانیتور |

تغییر حالت از Dashboard: `POST /api/v1/live/mode`

## مدیریت خطا

| خطا | رفتار |
|-----|--------|
| API exchange down | retry 3x با backoff → alert در Dashboard |
| Rate limit | wait + retry |
| Telegram fail | retry → ذخیره در DB → flag برای resend |
| Provider exception | log + skip آن Provider — ادامه با بقیه |
| FeatureBuilder exception | abort cycle + alert، چون همه Providerها به FeatureSet وابسته‌اند |

## Health Check

```
GET /api/v1/live/status

{
  "status": "running",
  "mode": "live",
  "last_run": "2026-07-06T10:01:00Z",
  "last_signal": "2026-07-06T08:30:00Z",
  "exchange_connected": true,
  "telegram_connected": true,
  "active_jobs": [
    {"symbol": "BTC/USDT", "timeframe": "1h", "next_run": "..."}
  ]
}
```

## امنیت

- API keys فقط در environment variables
- Telegram bot فقط **send** به کانال مشخص — بدون دریافت دستور از عموم
- IP whitelist برای exchange API (در صورت امکان)
- لاگ بدون ذخیره secrets

## تفاوت Validation و Live — چک‌لیست

| مورد | Validation | Live | یکسان؟ |
|------|--------|------|--------|
| PlatformRuntime | ✓ | ✓ | ✅ |
| FeatureBuilder | ✓ | ✓ | ✅ |
| DecisionEngine | ✓ | ✓ | ✅ |
| SignalProviders | ✓ | ✓ | ✅ |
| RiskManager | ✓ | ✓ | ✅ |
| MarketDataProvider | CSV | API | ❌ adapter |
| DecisionSink | SimulatedTradeSink | DB/WS/Telegram | ❌ adapter |
| Timing | batch | scheduled | ❌ |

## Paper Trading (توصیه)

قبل از Telegram واقعی:

1. حداقل 2–4 هفته در حالت `paper`
2. مقایسه سیگنال‌های paper با حرکت واقعی بازار
3. بررسی latency و پایداری API
4. سپس switch به `live`
