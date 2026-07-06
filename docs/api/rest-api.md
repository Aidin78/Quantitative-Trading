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

## Decisions

Decision موجودیت اصلی API است. هر cycle یک Decision تولید می‌کند: `approved` یا `rejected`.

### GET `/decisions`

لیست تمام تصمیم‌ها با فیلتر و pagination.

| Param | Type | توضیح |
|-------|------|--------|
| `symbol` | string | فیلتر نماد |
| `result` | string | approved \| rejected |
| `side` | string | BUY \| SELL، فقط برای approved |
| `rejection_reason` | string | risk \| filter \| low_confidence \| conflict |
| `provider` | string | فیلتر Provider مشارکت‌کننده |
| `start_date` | date | از تاریخ |
| `end_date` | date | تا تاریخ |
| `page` | int | صفحه |
| `limit` | int | تعداد |

```json
{
  "items": [
    {
      "id": "dec_abc123",
      "symbol": "BTC/USDT",
      "timeframe": "1h",
      "result": "approved",
      "side": "BUY",
      "confidence": 0.78,
      "rejection_reason": null,
      "provider_ids": ["ema_crossover", "rsi_divergence"],
      "feature_set_version": "v1",
      "timestamp": "2026-07-06T10:30:00Z"
    }
  ],
  "total": 142,
  "page": 1,
  "limit": 50
}
```

### GET `/decisions/{id}`

جزئیات کامل یک تصمیم شامل `FeatureSet`, `MarketContext`, provider votes و `DecisionLog`.

```json
{
  "id": "dec_abc123",
  "result": "approved",
  "final_signal": {
    "id": "sig_abc123",
    "side": "BUY",
    "entry_price": 67250.0,
    "stop_loss": 66800.0,
    "take_profit": 68500.0,
    "risk_reward": 2.78
  },
  "feature_snapshot": {
    "version": "v1",
    "indicators": { "rsi_14": 28.5, "ema_12": 67100.0 },
    "flags": { "ema_cross_bullish": true }
  },
  "market_context": {
    "trend": "UP",
    "volatility": "NORMAL",
    "atr": 450.0,
    "session": "EUROPE"
  },
  "provider_signals": [
    { "provider_id": "ema_crossover", "side": "BUY", "confidence": 0.75 },
    { "provider_id": "rsi_divergence", "side": "BUY", "confidence": 0.68 }
  ],
  "decision_log": {
    "market_filter": { "passed": true },
    "aggregation": { "side": "BUY", "confidence": 0.78 },
    "risk_check": { "passed": true }
  }
}
```

### GET `/engine/stats`

آمار Decision Monitor.

```json
{
  "decisions_today": 48,
  "approval_rate": 0.184,
  "rejection_breakdown": {
    "risk": 12,
    "market_filter": 18,
    "low_confidence": 9
  },
  "active_providers": 5,
  "feature_set_version": "v1"
}
```

---

## Signals

`Signal` یک view مشتق‌شده از Decisionهای `approved` است؛ rejectedها در `/decisions` می‌مانند.

### GET `/signals`

لیست فقط سیگنال‌های نهایی approved.

### GET `/signals/{id}`

جزئیات سیگنال به همراه `decision_id` برای مشاهده مسیر تصمیم.

---

## Features

### GET `/features/config`

برگرداندن `config/features.yaml`.

### PATCH `/features/config`

ویرایش controlled config برای اندیکاتورها و flags. تغییر config باید version جدید بسازد.

### GET `/features/snapshot`

آخرین `FeatureSet` برای symbol/timeframe.

---

## Providers

### GET `/providers`

```json
{
  "items": [
    {
      "provider_id": "ema_crossover",
      "name": "EMA Crossover Provider",
      "enabled": true,
      "weight": 1.0,
      "params": { "min_confidence": 0.6 },
      "required_features": ["ema_cross_bullish", "ema_12", "ema_26"]
    }
  ]
}
```

### PATCH `/providers/{id}`

```json
{
  "enabled": true,
  "weight": 1.2,
  "params": { "min_confidence": 0.65 }
}
```

Provider config نباید period اندیکاتور را تغییر دهد؛ آن در `/features/config` است.

---

## Validation

### POST `/validation/run`

اجرای ValidationHarness async.

```json
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "initial_capital": 10000,
  "commission_pct": 0.1,
  "slippage_pct": 0.05,
  "providers": ["ema_crossover", "rsi_divergence"],
  "feature_set_version": "v1",
  "engine_config_version": "v1"
}
```

### GET `/validation/{id}`

```json
{
  "id": "val_xyz789",
  "status": "completed",
  "progress": 100,
  "engine_metrics": {
    "approval_rate": 0.18,
    "rejection_breakdown": { "risk": 120, "low_confidence": 340 },
    "provider_contribution": { "ema_crossover": 0.62 }
  },
  "outcome_metrics": {
    "win_rate": 0.58,
    "profit_factor": 1.72,
    "sharpe_ratio": 1.35,
    "max_drawdown_pct": -12.4,
    "total_trades": 234
  }
}
```

### GET `/validation/{id}/decisions`

تمام DecisionRecordهای validation.

### GET `/validation/{id}/trades`

معاملات شبیه‌سازی‌شده از approved decisions.

### GET `/validation/{id}/equity-curve`

منحنی equity بر اساس simulated trades.

### DELETE `/validation/{id}`

حذف نتایج validation.

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
