# معاملات زنده (Live Trading)

## هدف

اجرای همان Decision Engine روی داده real-time و ارسال سیگنال‌های تأییدشده از طریق Telegram و Dashboard.

## پیش‌شرط

- بک‌تست با معیارهای قبولی انجام شده
- پارامترها و قوانین ریسک finalize شده
- **هیچ تغییری در منطق Engine** نسبت به بک‌تست

## معماری لایو

```
APScheduler
    │
    ├── Job: BTC/USDT 1h  (هر ساعت)
    ├── Job: BTC/USDT 4h  (هر 4 ساعت)
    └── Job: ETH/USDT 1h
            │
            ▼
    LiveRunner.execute(symbol, timeframe)
            │
            ▼
    LiveProvider.get_latest()
            │
            ▼
    Strategies → DecisionEngine → FinalSignal?
            │
    ┌───────┼───────┐
    ▼       ▼       ▼
   DB    Redis   Telegram
            │
            ▼
       WebSocket → Dashboard
```

## LiveRunner

```python
class LiveRunner:
    def __init__(
        self,
        data_provider: LiveProvider,
        strategies: list[BaseStrategy],
        engine: DecisionEngine,
        notifier: TelegramNotifier,
        signal_repo: SignalRepository,
    ): ...

    async def execute(self, symbol: str, timeframe: str) -> None:
        df = await self.data_provider.get_latest(symbol, timeframe)
        context = build_market_context(df, symbol, timeframe)
        portfolio = await self._load_portfolio_state()

        signals = [s.analyze(df, context) for s in self.strategies if s.enabled]
        final = self.engine.process(signals, context, portfolio)

        await self._log_decision(signals, context, final)

        if final:
            await self.signal_repo.save(final)
            await self.notifier.send(final)
            await self._publish_ws(final)
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
✅ Strategies: EMA Cross, RSI Div
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
| **paper** | سیگنال تولید و لاگ — بدون Telegram |
| **live** | Telegram + Dashboard |
| **paused** | Scheduler متوقف — فقط مانیتور |

تغییر حالت از Dashboard: `POST /api/v1/live/mode`

## مدیریت خطا

| خطا | رفتار |
|-----|--------|
| API exchange down | retry 3x با backoff → alert در Dashboard |
| Rate limit | wait + retry |
| Telegram fail | retry → ذخیره در DB → flag برای resend |
| Strategy exception | log + skip آن استراتژی — ادامه با بقیه |

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

## تفاوت بک‌تست و لایو — چک‌لیست

| مورد | بک‌تست | لایو | یکسان؟ |
|------|--------|------|--------|
| DecisionEngine | ✓ | ✓ | ✅ |
| Strategies | ✓ | ✓ | ✅ |
| RiskManager | ✓ | ✓ | ✅ |
| MarketDataProvider | CSV | API | ❌ adapter |
| Output | Metrics | Telegram/WS | ❌ handler |
| Timing | batch | scheduled | ❌ |

## Paper Trading (توصیه)

قبل از Telegram واقعی:

1. حداقل 2–4 هفته در حالت `paper`
2. مقایسه سیگنال‌های paper با حرکت واقعی بازار
3. بررسی latency و پایداری API
4. سپس switch به `live`
