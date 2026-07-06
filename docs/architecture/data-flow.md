# جریان داده (Data Flow)

> همه مسیرها از **PlatformRuntime** عبور می‌کنند. تفاوت Validation و Live فقط در adapter است.

## چرخه واحد — PlatformRuntime

```
MarketDataProvider.get_latest()
        │
        ▼
FeatureBuilder.build(df)  →  FeatureSet + MarketContext
        │
        ├──► Provider A.analyze(features, ctx) ──► StrategySignal
        ├──► Provider B.analyze(features, ctx) ──► StrategySignal
        └──► Provider N.analyze(features, ctx) ──► StrategySignal
                │
                ▼
        DecisionEngine.process()
                │
        ┌───────┴────────┐
        ▼                ▼
   Decision          Decision
   (approved)        (rejected)
        │                │
        ▼                ▼
   DecisionSink.handle(decision)  ← همیشه (شامل log ردشده‌ها)
```

## Validation — iterate روی تاریخ (بک‌تست)

```
CSV Files → CSVProvider
        │
        ▼
ValidationHarness (loop over history)
        │
        └──► PlatformRuntime.run_cycle()  ← همان Runtime
                    │
                    ▼
            SimulatedTradeSink (فقط approved)
                    │
        ▼ (end of data)
Engine Metrics + Outcome Metrics
        │
        ▼
Report (approval rate, rejection breakdown, Sharpe, Max DD, ...)
```

### گام‌به‌گام

1. **Harness** — CSV را iterate می‌کند (نه logic جدا از Runtime)
2. **Cycle** — هر نقطه زمانی یک `run_cycle()` کامل
3. **Decide** — Engine تصمیم می‌گیرد؛ rejected هم log می‌شود
4. **Simulate** — SimulatedTradeSink فقط approved را به معامله تبدیل می‌کند
5. **Metrics** — هم کیفیت تصمیم Engine، هم PnL outcome

## Live — همان Runtime، adapter متفاوت

```
Scheduler (every 1m / 5m / 1h)
        │
        ▼
LiveProvider (ccxt)
        │
        ▼
PlatformRuntime.run_cycle()  ← همان Runtime
        │
        ▼
CompositeSink
    ├── DatabaseSink (همه decisions)
    ├── WebSocketSink → Dashboard
    └── TelegramSink (فقط approved)
```

### تفاوت‌های کلیدی با بک‌تست

| جنبه | بک‌تست | لایو |
|------|--------|------|
| منبع داده | CSV (ثابت) | API (متغیر) |
| زمان | گذشته — iterate سریع | حال — wait for candle close |
| خروجی | Metrics file / DB | Telegram + WS + DB |
| خطا | fail fast | retry + alert |
| لاگ rejected | اختیاری | اجباری |

## Dashboard — جریان درخواست

### خواندن سیگنال‌ها (REST)

```
Browser → GET /api/v1/signals?symbol=BTC&limit=50
              │
              ▼
         FastAPI handler
              │
              ▼
         SignalRepository.query()
              │
              ▼
         PostgreSQL
              │
              ▼
         JSON Response → React Query cache → UI Table
```

### سیگنال لحظه‌ای (WebSocket)

```
Live Runner emits signal
        │
        ▼
Redis PUBLISH channel:signals
        │
        ▼
FastAPI WebSocket manager
        │
        ▼
All connected clients
        │
        ▼
useSignalFeed hook → toast + invalidate cache
```

### اجرای بک‌تست (Async)

```
Browser → POST /api/v1/validation/run { config }
              │
              ▼
         Create job in DB (status: pending)
              │
              ▼
         Celery / Background task
              │
              ├──► WS: progress 10%, 20%, ...
              ├──► Run ValidationHarness
              └──► WS: complete + results
                        │
                        ▼
                   Browser navigates to /validation/results/{id}
```

## مدل‌های داده — روابط

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Validation  │────►│   Trade     │     │   Decision  │
│  Run        │ 1:N │             │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
┌─────────────┐     ┌─────────────┐            │ N:1
│  Provider   │◄────│ Provider    │◄───────────┘
│  Config     │     │ Signal      │
└─────────────┘     └─────────────┘

Decision ──► contains FeatureSet snapshot + ProviderSignals + DecisionLog
Signal (final) ──► exists only for approved Decisions
Trade ──► linked to one approved Decision / Signal
ValidationRun ──► contains many Decisions and simulated Trades
```

## MarketContext

شیء کمکی که به Engine و استراتژی‌ها داده می‌شود:

```python
@dataclass
class MarketContext:
    symbol: str
    timeframe: str
    current_price: float
    trend: Literal["UP", "DOWN", "SIDEWAYS"]
    volatility: Literal["LOW", "NORMAL", "HIGH"]
    atr: float
    session: Literal["ASIA", "EUROPE", "US", "OVERLAP"]
    timestamp: datetime
```

در بک‌تست از داده تاریخی محاسبه می‌شود؛ در لایو از آخرین کندل‌ها و اندیکاتورها.

## Decision Log (شفافیت)

هر بار که Engine فراخوانی می‌شود، حتی اگر سیگنال رد شود:

```json
{
  "timestamp": "2026-07-06T10:30:00Z",
  "symbol": "BTC/USDT",
  "strategy_signals": [...],
  "market_filter": { "passed": true, "reason": null },
  "aggregation": { "consensus": "BUY", "avg_confidence": 0.72 },
  "risk_check": { "passed": false, "reason": "daily_drawdown_limit" },
  "final_signal": null
}
```

این لاگ در Dashboard بخش Live Monitor و جزئیات Signal نمایش داده می‌شود.
