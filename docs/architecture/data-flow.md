# جریان داده (Data Flow)

> همه مسیرها از **PlatformRuntime** عبور می‌کنند. تفاوت Validation و Live فقط در adapter است.
>
> مرجع: [execution-model.md](./execution-model.md) | [state-risk-contract.md](./state-risk-contract.md)

## چرخه واحد — PlatformRuntime

```
MarketDataProvider.get_latest()
        │
        ▼
FeatureBuilder.build(df)  →  FeatureSet + MarketContext
        │                      └──► FeatureStore.put()
        ▼
StateStore.snapshot()  →  state_snapshot_id
        │
        ├──► Provider A.analyze(features, ctx) ──► ProviderOpinion
        ├──► Provider B.analyze(features, ctx) ──► ProviderOpinion
        └──► Provider N.analyze(features, ctx) ──► ProviderOpinion
                │
                ▼
        DecisionEngine.process(signals, context, snapshot)  ← read-only risk
                │
        ┌───────┴────────┐
        ▼                ▼
   DecisionApproved   DecisionRejected
        │                │
        ▼                ▼
   ExecutionEngine     EventBus (DecisionRejected)
   OrderIntent → Fill
        │
        ▼
   StateStore.apply_transition()
        │
        ▼
   EventBus.publish(EventEnvelope)  ← Market → Signal → Decision → Execution
```

## Validation — iterate روی تاریخ

```
CSV Files → CSVProvider
        │
        ▼
ValidationHarness (loop over history)
        │
        └──► PlatformRuntime.run_cycle()  ← همان Runtime
                    │
                    ▼
            EventBus
                ├── ExecutionEngine (Simulated) → FillReceived → PositionClosed
                ├── event_log_handler → event_log
                └── database_handler → decisions
                    │
        ▼ (end of data)
Engine Metrics + Outcome Metrics
        │
        ▼
Report (approval rate, rejection breakdown, Sharpe, Max DD, ...)
```

### گام‌به‌گام

1. **Harness** — CSV را iterate می‌کند
2. **Cycle** — هر نقطه زمانی یک `run_cycle()` کامل
3. **Snapshot** — `StateStore.snapshot()` قبل از تصمیم
4. **Decide** — Engine؛ rejected هم log می‌شود
5. **Execute** — `SimulatedExecutionEngine` برای approved
6. **State** — `apply_transition` پس از `FillReceived`
7. **Metrics** — کیفیت تصمیم Engine + PnL outcome

## Live — همان Runtime، adapter متفاوت

```
Scheduler (cron per symbol/timeframe)
        │
        ▼
LiveProvider (ccxt)
        │
        ▼
PlatformRuntime.run_cycle()  ← همان Runtime
        │
        ▼
EventBus (Redis adapter)
    ├── DatabaseEventHandler (همه decisions + event_log)
    ├── WebSocketEventHandler → Dashboard
    ├── MetricsEventHandler
    ├── ExecutionEngine (Paper/Live — فاز آینده)
    └── TelegramEventHandler (فقط SignalPublished — notification)
```

### تفاوت‌های کلیدی با validation

| جنبه | validation | live |
|------|------------|------|
| منبع داده | CSV (ثابت) | API (متغیر) |
| زمان | گذشته — iterate سریع | حال — wait for candle close |
| Execution | `SimulatedExecutionEngine` | Paper/Live (فاز 7) |
| EventBus | InMemory | Redis |
| Handlerها | DB + event_log | DB + WS + Telegram |
| خطا | fail fast | retry + alert |
| Governance | `revision_id` در config | `LiveGovernanceGate` |

## Dashboard — جریان درخواست

### خواندن تصمیم‌ها (REST)

```
Browser → GET /api/v1/decisions?symbol=BTC&limit=50
              │
              ▼
         FastAPI → DecisionRepository → PostgreSQL → JSON
```

### تصمیم لحظه‌ای (WebSocket)

```
EventBus → WebSocketEventHandler
              │
              ▼
         /ws/decisions  (DecisionApproved / DecisionRejected)
              │
              ▼
         useDecisionFeed → toast + invalidate cache
```

### اجرای validation (Async)

```
Browser → POST /api/v1/validation/run { config, revision_id }
              │
              ▼
         ValidationHarness → WS progress → results page
```

## مدل‌های داده — روابط

```
ConfigRevision ──► Experiment ──► ExperimentRun
                                      │
                                      ▼
ValidationRun ──► Decision ──► Order ──► Fill ──► Position
                     │
                     ├── FeatureSetRecord (feature_store)
                     ├── StateSnapshot (state_snapshots)
                     └── event_log (full chain)
```

## Decision Log (شفافیت)

هر cycle — حتی rejected:

```json
{
  "event_time": "2026-07-06T10:00:00Z",
  "decision_time": "2026-07-06T10:00:01.890Z",
  "state_snapshot_id": "snap_001",
  "revision_id": "rev_baseline",
  "market_filter": { "passed": true },
  "aggregation": { "side": "BUY", "confidence": 0.72 },
  "risk_check": { "passed": false, "checks": [...] },
  "final_signal": null
}
```

جزئیات: [explainability.md](./explainability.md)
