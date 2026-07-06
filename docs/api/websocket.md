# WebSocket API

Base URL: `ws://localhost:8000` (یا `wss://` در production)

Authentication: query param `?token=<JWT>` یا header در handshake

## Endpoints

| Endpoint | کاربرد |
|----------|--------|
| `/ws/signals` | سیگنال‌های جدید |
| `/ws/backtest/{job_id}` | progress بک‌تست |
| `/ws/live` | feed لایو (decisions + status) |

---

## `/ws/signals`

### اتصال

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/signals?token=eyJ...');
```

### Events (Server → Client)

#### `signal.new`

سیگنال جدید صادر شد.

```json
{
  "event": "signal.new",
  "data": {
    "id": "sig_abc123",
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

#### `signal.rejected`

سیگنال رد شد (برای decision log).

```json
{
  "event": "signal.rejected",
  "data": {
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

## `/ws/backtest/{job_id}`

### Events

#### `backtest.progress`

```json
{
  "event": "backtest.progress",
  "data": {
    "job_id": "bt_xyz789",
    "progress": 45,
    "current_date": "2024-06-15",
    "trades_so_far": 89
  }
}
```

#### `backtest.completed`

```json
{
  "event": "backtest.completed",
  "data": {
    "job_id": "bt_xyz789",
    "metrics": {
      "win_rate": 0.58,
      "profit_factor": 1.72,
      "sharpe_ratio": 1.35,
      "max_drawdown_pct": -12.4,
      "total_trades": 234
    }
  }
}
```

#### `backtest.failed`

```json
{
  "event": "backtest.failed",
  "data": {
    "job_id": "bt_xyz789",
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

## معماری Pub/Sub

```
LiveRunner
    │
    ▼
Redis PUBLISH
    ├── channel:signals     → /ws/signals clients
    ├── channel:live        → /ws/live clients
    └── channel:backtest:*  → /ws/backtest/{id} clients
```

FastAPI WebSocket Manager:

```python
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, channel: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(channel, []).append(ws)

    async def broadcast(self, channel: str, message: dict):
        for ws in self.active.get(channel, []):
            await ws.send_json(message)
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
