# WebSocket API

Base URL: `ws://localhost:8000` (یا `wss://` در production)

Authentication: query param `?token=<JWT>` یا header در handshake

## Endpoints

| Endpoint | کاربرد |
|----------|--------|
| `/ws/decisions` | stream تمام decisionها (approved + rejected) |
| `/ws/signals` | فقط سیگنال‌های approved برای اعلان UI |
| `/ws/validation/{job_id}` | progress validation |
| `/ws/live` | status لایو و runtime events |

---

## `/ws/decisions`

### اتصال

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/decisions?token=eyJ...');
```

### Events (Server → Client)

#### `decision.created`

هر cycle یک decision جدید تولید می‌کند.

```json
{
  "event": "decision.created",
  "data": {
    "id": "dec_abc123",
    "symbol": "BTC/USDT",
    "result": "approved",
    "side": "BUY",
    "confidence": 0.78,
    "rejection_reason": null,
    "provider_ids": ["ema_crossover", "rsi_divergence"],
    "feature_set_version": "v1",
    "timeframe": "1h",
    "timestamp": "2026-07-06T10:30:00Z"
  }
}
```

#### `decision.rejected`

تصمیم rejected شد؛ UI باید دلیل را در Decision Monitor نمایش دهد.

```json
{
  "event": "decision.rejected",
  "data": {
    "id": "dec_rej_001",
    "symbol": "BTC/USDT",
    "reason": "daily_drawdown_limit",
    "timestamp": "2026-07-06T10:30:00Z",
    "decision_log": { ... }
  }
}
```

### Client → Server

#### `ping`

```json
{ "event": "ping" }
```

#### `pong` (response)

```json
{ "event": "pong", "timestamp": "2026-07-06T10:30:00Z" }
```

---

## `/ws/signals`

فقط برای approved decisions و toast اعلان سیگنال استفاده می‌شود. منبع truth همچنان `/ws/decisions` است.

#### `signal.new`

```json
{
  "event": "signal.new",
  "data": {
    "id": "sig_abc123",
    "decision_id": "dec_abc123",
    "symbol": "BTC/USDT",
    "side": "BUY",
    "entry_price": 67250.0,
    "stop_loss": 66800.0,
    "take_profit": 68500.0,
    "confidence": 0.78,
    "timeframe": "1h",
    "timestamp": "2026-07-06T10:30:00Z"
  }
}
```

---

## `/ws/validation/{job_id}`

### Events

#### `validation.progress`

```json
{
  "event": "validation.progress",
  "data": {
    "job_id": "val_xyz789",
    "progress": 45,
    "current_date": "2024-06-15",
    "trades_so_far": 89
  }
}
```

#### `validation.completed`

```json
{
  "event": "validation.completed",
  "data": {
    "job_id": "val_xyz789",
    "engine_metrics": {
      "approval_rate": 0.18,
      "rejection_breakdown": { "risk": 120, "low_confidence": 340 }
    },
    "outcome_metrics": {
      "win_rate": 0.58,
      "profit_factor": 1.72,
      "sharpe_ratio": 1.35,
      "max_drawdown_pct": -12.4,
      "total_trades": 234
    }
  }
}
```

#### `validation.failed`

```json
{
  "event": "validation.failed",
  "data": {
    "job_id": "val_xyz789",
    "error": "Insufficient data for warmup period"
  }
}
```

---

## `/ws/live`

### Events

#### `live.status`

تغییر وضعیت سیستم.

```json
{
  "event": "live.status",
  "data": {
    "status": "running",
    "mode": "live",
    "exchange_connected": true
  }
}
```

#### `live.decision`

هر تصمیم Engine (شامل rejected).

```json
{
  "event": "live.decision",
  "data": {
    "timestamp": "2026-07-06T10:30:00Z",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "result": "approved",
    "final_signal": { ... },
    "decision_log": { ... }
  }
}
```

#### `live.candle`

کندل جدید (اختیاری — برای چارت زنده).

```json
{
  "event": "live.candle",
  "data": {
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "candle": {
      "timestamp": "2026-07-06T10:00:00Z",
      "open": 67100,
      "high": 67400,
      "low": 66900,
      "close": 67250,
      "volume": 1234.5
    }
  }
}
```

---

## معماری EventBus / Pub/Sub

```
PlatformRuntime
    │
    ▼
EventBus.publish(DomainEvent)
    │
    ├── DecisionCreated     → WebSocketEventHandler → /ws/decisions
    ├── SignalApproved      → WebSocketEventHandler → /ws/signals
    ├── ValidationProgressed → WebSocketEventHandler → /ws/validation/{id}
    └── LiveStatusChanged   → WebSocketEventHandler → /ws/live
```

در MVP، `InMemoryEventBus` کافی است. در Live، همین EventBus می‌تواند Redis Pub/Sub یا Redis Streams adapter داشته باشد.

FastAPI WebSocket Handler:

```python
class WebSocketEventHandler:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def handle(self, event: DomainEvent) -> None:
        channel = self._route_event(event)
        for ws in self.active.get(channel, []):
            await ws.send_json(event_to_ws_message(event))
```

---

## Reconnection Strategy (Frontend)

```typescript
function useWebSocket(url: string) {
  const [status, setStatus] = useState<'connected' | 'disconnected'>('disconnected');
  const reconnectDelay = useRef(1000);

  const connect = useCallback(() => {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setStatus('connected');
      reconnectDelay.current = 1000;
    };

    ws.onclose = () => {
      setStatus('disconnected');
      setTimeout(connect, reconnectDelay.current);
      reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000);
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      handleEvent(msg);
    };
  }, [url]);

  useEffect(() => { connect(); }, [connect]);

  return { status };
}
```

- Exponential backoff: 1s → 2s → 4s → ... → max 30s
- نمایش badge «Reconnecting...» در header
- پس از reconnect، React Query cache invalidate

---

## Heartbeat

- Client هر 30 ثانیه `ping` می‌فرستد
- Server اگر 60 ثانیه پیامی نگیرد connection را می‌بندد
- Client با reconnect دوباره وصل می‌شود

---

## محدودیت‌ها

| مورد | مقدار |
|------|-------|
| Max connections per user | 5 |
| Max message size | 64 KB |
| Rate limit | 100 messages/min per connection |
