# معاملات زنده (Live Trading)

## هدف

اجرای همان `PlatformRuntime` روی داده real-time. خروجی‌ها فقط از طریق **EventBus → Handlers** — نه فراخوانی مستقیم DB/Telegram.

## پیش‌شرط

- Validation با `revision_id` مشخص و معیارهای قبولی — [governance.md](../architecture/governance.md)
- `LiveGovernanceGate.allow_start(revision_id)` = true
- **همان** Feature Builder، Runtime و Engine نسبت به validation

## معماری لایو

```
APScheduler
    │
    └──► PlatformRuntime.run_cycle(symbol, timeframe)
              │
              ├── LiveProvider.get_latest()
              ├── FeatureBuilder → FeatureStore
              ├── StateStore.snapshot()
              ├── Providers → DecisionEngine (snapshot read-only)
              ├── ExecutionEngine (paper/live — فاز 7)
              │
              ▼
         EventBus (Redis)
              │
    ┌─────────┼─────────┬─────────────┐
    ▼         ▼         ▼             ▼
   DB      WebSocket  Telegram    Metrics
```

**قانون:** Runtime هیچ import مستقیم از Telegram/DB/WebSocket ندارد.

## Scheduler + Runtime

```python
# scripts/run_live.py
scheduler = AsyncIOScheduler()

async def run_job(symbol: str, timeframe: str) -> None:
    await platform_runtime.run_cycle(symbol=symbol, timeframe=timeframe)

scheduler.add_job(
    run_job,
    "cron",
    minute=1,
    kwargs={"symbol": "BTC/USDT", "timeframe": "1h"},
)
```

`PlatformRuntime` همان کلاس validation است — فقط adapterها عوض می‌شوند.

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

## Telegram (EventHandler)

`TelegramEventHandler` فقط روی `SignalPublished` واکنش نشان می‌دهد — پس از `PositionOpened` یا به‌عنوان notification جدا از fill.

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

## حالت‌های اجرا

| حالت | توضیح |
|------|--------|
| **paper** | Decision + execution شبیه‌سازی — بدون Telegram |
| **live** | DB + WebSocket + Telegram برای approved |
| **paused** | Scheduler متوقف |

تغییر حالت: `POST /api/v1/live/mode`

## مدیریت خطا

| خطا | رفتار |
|-----|--------|
| API exchange down | retry 3x → `RuntimeCycleFailed` event → alert |
| Rate limit | wait + retry |
| Telegram fail | retry → DB queue → `SignalPublished` با flag resend |
| Provider exception | `ProviderSkipped` event — ادامه با بقیه |
| FeatureBuilder exception | abort cycle + `RuntimeCycleFailed` |

## Health Check

```
GET /api/v1/live/status

{
  "status": "running",
  "mode": "live",
  "revision_id": "rev_baseline",
  "experiment_id": "exp_live_001",
  "last_run": "2026-07-06T10:01:00Z",
  "exchange_connected": true,
  "alerts_connected": true,
}
```

## تفاوت Validation و Live

| مورد | Validation | Live | یکسان؟ |
|------|------------|------|--------|
| `PlatformRuntime` | ✓ | ✓ | ✅ |
| `DecisionEngine` | ✓ | ✓ | ✅ |
| `StateStore` schema | ✓ | ✓ | ✅ |
| `MarketDataProvider` | CSV | ccxt | adapter |
| `EventBus` | InMemory | Redis | adapter |
| `ExecutionEngine` | Simulated | Paper/Live | adapter |
| `EventHandlers` | DB + event_log | DB + WS + Telegram | adapter |
| Timing | batch | scheduled | adapter |

## Paper Trading (توصیه)

1. حداقل 2–4 هفته `paper` با `revision_id` ثابت
2. مقایسه با validation همان revision
3. بررسی latency (`decision_time - event_time`)
4. سپس `live` + `LiveGovernanceGate`
