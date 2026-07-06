# REST API

Base URL: `/api/v1`

Authentication: `Authorization: Bearer <JWT>` (به‌جز `/auth/login`)

## Auth

### POST `/auth/login`

```json
// Request
{
  "username": "admin",
  "password": "..."
}

// Response 200
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### POST `/auth/refresh`

```json
// Response 200
{
  "access_token": "eyJ...",
  "expires_in": 3600
}
```

---

## Signals

### GET `/signals`

لیست سیگنال‌ها با فیلتر و pagination.

**Query Parameters:**

| Param | Type | Default | توضیح |
|-------|------|---------|--------|
| `symbol` | string | — | فیلتر نماد |
| `side` | string | — | BUY \| SELL |
| `status` | string | — | sent \| rejected \| paper |
| `strategy` | string | — | فیلتر استراتژی |
| `min_confidence` | float | — | حداقل confidence |
| `start_date` | date | — | از تاریخ |
| `end_date` | date | — | تا تاریخ |
| `page` | int | 1 | صفحه |
| `limit` | int | 50 | تعداد (max 100) |

```json
// Response 200
{
  "items": [
    {
      "id": "sig_abc123",
      "symbol": "BTC/USDT",
      "side": "BUY",
      "entry_price": 67250.0,
      "stop_loss": 66800.0,
      "take_profit": 68500.0,
      "confidence": 0.78,
      "risk_reward": 2.78,
      "timeframe": "1h",
      "status": "sent",
      "contributing_strategies": ["ema_crossover", "rsi_divergence"],
      "timestamp": "2026-07-06T10:30:00Z"
    }
  ],
  "total": 142,
  "page": 1,
  "limit": 50,
  "pages": 3
}
```

### GET `/signals/{id}`

جزئیات کامل یک سیگنال شامل decision log و strategy signals.

```json
// Response 200
{
  "id": "sig_abc123",
  "symbol": "BTC/USDT",
  "side": "BUY",
  "entry_price": 67250.0,
  "stop_loss": 66800.0,
  "take_profit": 68500.0,
  "confidence": 0.78,
  "risk_reward": 2.78,
  "timeframe": "1h",
  "status": "sent",
  "timestamp": "2026-07-06T10:30:00Z",
  "market_context": {
    "trend": "UP",
    "volatility": "NORMAL",
    "atr": 450.0,
    "session": "EUROPE"
  },
  "contributing_strategies": ["ema_crossover", "rsi_divergence"],
  "strategy_signals": [
    {
      "strategy_id": "ema_crossover",
      "side": "BUY",
      "confidence": 0.75,
      "metadata": { "fast_ema": 67100, "slow_ema": 66800 }
    }
  ],
  "decision_log": {
    "market_filter": { "passed": true },
    "aggregation": { "side": "BUY", "confidence": 0.78 },
    "risk_check": { "passed": true }
  }
}
```

### GET `/signals/stats`

آمار کلی برای KPI cards.

```json
// Response 200
{
  "signals_today": 3,
  "signals_week": 12,
  "win_rate_30d": 0.624,
  "profit_30d_pct": 4.2,
  "max_drawdown_30d_pct": -8.1,
  "active_strategies": 5,
  "total_strategies": 7
}
```

---

## Strategies

### GET `/strategies`

```json
// Response 200
{
  "items": [
    {
      "strategy_id": "ema_crossover",
      "name": "EMA Crossover",
      "enabled": true,
      "weight": 1.0,
      "params": { "fast_period": 12, "slow_period": 26 },
      "stats": {
        "win_rate": 0.58,
        "total_signals": 142,
        "avg_confidence": 0.71,
        "last_signal_at": "2026-07-06T08:30:00Z"
      }
    }
  ]
}
```

### GET `/strategies/{id}`

جزئیات + performance history.

### PATCH `/strategies/{id}`

```json
// Request
{
  "enabled": true,
  "weight": 1.2,
  "params": { "fast_period": 10, "slow_period": 24 }
}

// Response 200
{ "strategy_id": "ema_crossover", "enabled": true, ... }
```

---

## Backtest

### POST `/backtest/run`

شروع بک‌تست async.

```json
// Request
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "initial_capital": 10000,
  "commission_pct": 0.1,
  "slippage_pct": 0.05,
  "strategies": ["ema_crossover", "rsi_divergence"]
}

// Response 202
{
  "job_id": "bt_xyz789",
  "status": "pending"
}
```

### GET `/backtest/{id}`

```json
// Response 200
{
  "id": "bt_xyz789",
  "status": "completed",
  "progress": 100,
  "config": { ... },
  "metrics": {
    "win_rate": 0.58,
    "profit_factor": 1.72,
    "sharpe_ratio": 1.35,
    "max_drawdown_pct": -12.4,
    "total_trades": 234,
    "net_profit_pct": 18.5
  },
  "created_at": "2026-07-06T09:00:00Z",
  "completed_at": "2026-07-06T09:05:00Z"
}
```

### GET `/backtest/{id}/trades`

```json
// Response 200
{
  "items": [
    {
      "id": "trade_001",
      "symbol": "BTC/USDT",
      "side": "BUY",
      "entry_price": 42000,
      "exit_price": 43200,
      "entry_time": "2024-03-15T10:00:00Z",
      "exit_time": "2024-03-16T14:00:00Z",
      "pnl": 120.0,
      "pnl_pct": 2.86,
      "exit_reason": "TP"
    }
  ],
  "total": 234
}
```

### GET `/backtest/{id}/equity-curve`

```json
// Response 200
{
  "data": [
    { "timestamp": "2024-01-01T00:00:00Z", "equity": 10000 },
    { "timestamp": "2024-01-02T00:00:00Z", "equity": 10050 }
  ]
}
```

### DELETE `/backtest/{id}`

حذف نتایج بک‌تست.

---

## Live

### GET `/live/status`

```json
// Response 200
{
  "status": "running",
  "mode": "live",
  "exchange_connected": true,
  "telegram_connected": true,
  "last_run_at": "2026-07-06T10:01:00Z",
  "last_signal_at": "2026-07-06T08:30:00Z",
  "jobs": [
    {
      "symbol": "BTC/USDT",
      "timeframe": "1h",
      "next_run_at": "2026-07-06T11:01:00Z"
    }
  ]
}
```

### POST `/live/start`

### POST `/live/stop`

### POST `/live/mode`

```json
// Request
{ "mode": "paper" }  // paper | live
```

### GET `/live/decision-log`

```json
// Query: limit=20
{
  "items": [
    {
      "timestamp": "2026-07-06T10:30:00Z",
      "symbol": "BTC/USDT",
      "result": "rejected",
      "reason": "daily_drawdown_limit",
      "strategy_signals": [...],
      "decision_log": { ... }
    }
  ]
}
```

---

## Market

### GET `/market/ohlcv`

```json
// Query: symbol=BTC/USDT&timeframe=1h&limit=200

{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "data": [
    {
      "timestamp": "2026-07-06T09:00:00Z",
      "open": 67100,
      "high": 67400,
      "low": 66900,
      "close": 67250,
      "volume": 1234.5
    }
  ]
}
```

### GET `/market/context`

```json
// Query: symbol=BTC/USDT&timeframe=1h

{
  "symbol": "BTC/USDT",
  "current_price": 67250,
  "trend": "UP",
  "volatility": "NORMAL",
  "atr": 450.0,
  "atr_pct": 0.67,
  "session": "EUROPE"
}
```

---

## Analytics

### GET `/analytics/overview`

```json
// Query: period=30d

{
  "period": "30d",
  "total_signals": 45,
  "win_rate": 0.624,
  "profit_pct": 4.2,
  "max_drawdown_pct": -8.1,
  "sharpe_ratio": 1.2,
  "by_symbol": [...],
  "by_strategy": [...]
}
```

### GET `/analytics/heatmap`

```json
// Query: period=90d&type=hourly

{
  "data": [
    { "hour": 9, "day": "Monday", "win_rate": 0.65, "trades": 12 }
  ]
}
```

---

## Risk

### GET `/risk/rules`

### PATCH `/risk/rules`

```json
// Request
{
  "max_daily_drawdown_pct": 5.0,
  "max_signals_per_day": 10,
  "min_confidence": 0.65
}
```

### GET `/risk/status`

وضعیت فعلی نسبت به محدودیت‌ها.

---

## Error Responses

```json
// 400 Bad Request
{
  "detail": "Invalid date range",
  "code": "VALIDATION_ERROR"
}

// 401 Unauthorized
{
  "detail": "Invalid or expired token"
}

// 404 Not Found
{
  "detail": "Signal not found"
}

// 500 Internal Server Error
{
  "detail": "Internal server error",
  "code": "INTERNAL_ERROR"
}
```

## OpenAPI

مستندات تعاملی در:

```
GET http://localhost:8000/docs      # Swagger UI
GET http://localhost:8000/redoc     # ReDoc
GET http://localhost:8000/openapi.json
```
