# REST API

Base URL: `/api/v1`

Interactive docs: `GET /docs` (Swagger), `GET /redoc`, `GET /openapi.json`

## Authentication

Most routes use `Authorization: Bearer <JWT>`.

| Route | Auth |
|-------|------|
| `POST /auth/login` | Public |
| `GET /health`, `GET /metrics` | Public (no `/api/v1` prefix) |
| All other `/api/v1/*` | Bearer when `AUTH_REQUIRED=true`; optional in development (`anonymous`) |

WebSocket: `WS /ws/decisions?token=<jwt>` (token required when `AUTH_REQUIRED=true`).

---

## Endpoint index (implemented)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Issue JWT |
| POST | `/auth/refresh` | Refresh JWT |
| GET | `/decisions` | List decisions (filters + pagination) |
| GET | `/decisions/export` | CSV export |
| GET | `/decisions/{id}` | Decision detail |
| GET | `/signals` | Approved decisions as signals |
| GET | `/signals/{id}` | Signal detail (= approved decision) |
| GET | `/engine/config` | Engine YAML config |
| PATCH | `/engine/config` | Patch engine config + new revision |
| GET | `/engine/stats` | Dashboard aggregate stats |
| GET | `/providers` | Provider configs |
| PATCH | `/providers/{id}` | Update provider config |
| POST | `/validation/run` | Start async validation job |
| GET | `/validation/{id}` | Job status + metrics |
| GET | `/validation/{id}/export` | CSV export |
| POST | `/validation/walk-forward` | Rolling-window validation |
| GET | `/live/status` | Live runtime status |
| POST | `/live/start` | Start paper/live scheduler |
| POST | `/live/stop` | Stop scheduler |
| POST | `/live/mode` | Switch paper/live |
| GET | `/live/decision-log` | Recent live/paper decisions |
| GET | `/replay/cycle/{correlation_id}/timeline` | Replay timeline |
| GET | `/replay/cycle/{correlation_id}/graph` | Causal graph |
| POST | `/replay/cycle/{correlation_id}` | Replay (alias of timeline) |
| GET | `/experiments` | List experiments |
| POST | `/experiments` | Create experiment |
| GET | `/experiments/{id}` | Experiment detail |
| GET | `/config/revisions` | Config revision history |
| GET | `/config/revisions/{id}` | Revision bundle |
| GET | `/analytics/overview` | Decision analytics |
| GET | `/analytics/heatmap` | Approval heatmap |
| GET | `/health` | Health + phase |
| GET | `/metrics` | Prometheus metrics |

**Not implemented (future):** `/features/*`, `/market/*`, `/risk/*`, `/experiments/compare`, `/experiments/{id}/runs`, `/validation/{id}/decisions|trades|equity-curve`.

---

## Auth

### POST `/auth/login`

```json
// Request
{ "username": "admin", "password": "changeme" }

// Response 200
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### POST `/auth/refresh`

Requires valid Bearer token. Returns a new `access_token`.

---

## Decisions

### GET `/decisions`

| Param | Type | Description |
|-------|------|-------------|
| `symbol` | string | Filter symbol |
| `result` | string | `approved` \| `rejected` |
| `side` | string | `BUY` \| `SELL` |
| `rejection_reason` | string | Rejection reason |
| `provider` | string | Provider id in decision log |
| `start_date` | datetime | From |
| `end_date` | datetime | To |
| `page` | int | Page (default 1) |
| `limit` | int | Page size (default 50, max 200) |

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
      "rejection_stage": null,
      "provider_ids": ["ema_crossover"],
      "timestamp": "2026-07-06T10:30:00Z",
      "correlation_id": "cycle_btc_1h_xxx",
      "revision_id": "rev_...",
      "experiment_id": null
    }
  ],
  "total": 142,
  "page": 1,
  "limit": 50
}
```

### GET `/decisions/{id}`

Full detail: `decision_log`, `provider_signals`, `feature_snapshot`, `market_context`, `explainability`, `revision_id`, `experiment_id`.

### GET `/decisions/export`

Query: `format=csv` (required), `limit=1000` (max 5000). Returns CSV attachment.

---

## Signals

View over approved decisions only.

### GET `/signals`

Query: `symbol`, `page`, `limit`.

```json
{
  "items": [
    {
      "id": "dec_abc123",
      "decision_id": "dec_abc123",
      "symbol": "BTC/USDT",
      "side": "BUY",
      "confidence": 0.78,
      "timestamp": "2026-07-06T10:30:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "limit": 50
}
```

### GET `/signals/{id}`

Same payload as `GET /decisions/{id}`; 404 if not approved.

---

## Engine

### GET `/engine/config`

```json
{ "engine": { "aggregation": {}, "filter": {}, "risk": {} } }
```

### PATCH `/engine/config`

```json
// Request (all fields optional)
{
  "aggregation": { "method": "weighted_majority", "min_confidence": 0.6 },
  "filter": { "min_atr_pct": 0.1 },
  "risk": { "max_daily_drawdown_pct": 5.0 }
}

// Response
{ "engine": { ... }, "revision_id": "rev_..." }
```

### GET `/engine/stats`

```json
{
  "decisions_today": 48,
  "approval_rate": 0.184,
  "rejection_breakdown": { "risk": 12, "market_filter": 18 },
  "active_providers": 2,
  "feature_set_version": "v1"
}
```

---

## Providers

### GET `/providers`

```json
{
  "items": [
    {
      "provider_id": "ema_crossover",
      "name": "Ema Crossover",
      "enabled": true,
      "weight": 1.0,
      "params": { "min_confidence": 0.6 },
      "required_features": ["ema_cross_bullish"]
    }
  ]
}
```

### PATCH `/providers/{provider_id}`

```json
{ "enabled": true, "weight": 1.2, "params": { "min_confidence": 0.65 } }
```

---

## Validation

### POST `/validation/run`

Starts background job; poll `GET /validation/{id}`.

```json
// Request (all optional — defaults from config/settings.yaml)
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2026-01-01",
  "end_date": "2026-06-01",
  "csv_path": null,
  "revision_id": "rev_...",
  "experiment_id": "exp_..."
}

// Response 200
{ "id": "run_abc123", "status": "pending" }
```

### GET `/validation/{id}`

```json
{
  "id": "run_abc123",
  "status": "completed",
  "engine_metrics": { "approval_rate": 0.18, "rejection_breakdown": {} },
  "outcome_metrics": { "win_rate": 0.58, "total_trades": 234 },
  "run_id": "run_abc123",
  "revision_id": "rev_...",
  "experiment_id": null
}
```

Statuses: `pending`, `running`, `completed`, `failed`.

### POST `/validation/walk-forward`

```json
// Request
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2026-01-01",
  "end_date": "2026-06-01",
  "windows": 3,
  "train_ratio": 0.7
}

// Response
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "windows": [
    {
      "window": 0,
      "test_start": "2026-01-01T00:00:00+00:00",
      "test_end": "2026-02-15T00:00:00+00:00",
      "status": "completed",
      "engine_metrics": {},
      "outcome_metrics": {}
    }
  ]
}
```

### GET `/validation/{id}/export`

Query: `format=csv`. CSV of job metrics and config.

---

## Live

### GET `/live/status`

```json
{
  "status": "running",
  "mode": "paper",
  "exchange_connected": true,
  "alerts_connected": false,
  "last_run_at": "2026-07-06T10:01:00Z",
  "last_signal_at": null,
  "last_error": null,
  "revision_id": "rev_...",
  "experiment_id": null,
  "jobs": [{ "symbol": "BTC/USDT", "timeframe": "1h", "next_run_at": "..." }]
}
```

### POST `/live/start`

```json
{
  "mode": "paper",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "revision_id": "rev_...",
  "experiment_id": null
}
```

Returns updated status. May return `403` if `LiveGovernanceGate` blocks start (production without validated revision).

### POST `/live/stop`

Stops scheduler; returns status.

### POST `/live/mode`

```json
{ "mode": "paper" }
```

### GET `/live/decision-log`

Query: `limit=20` (max 100). Recent `DECISION_APPROVED` / `DECISION_REJECTED` events in paper/live mode.

---

## Replay

[replay-engine.md](../architecture/replay-engine.md)

### GET `/replay/cycle/{correlation_id}/timeline`

Query: `mode=strict|re_execute`, `revision_id` (optional, re-execute only).

```json
{
  "correlation_id": "cycle_btc_1h_xxx",
  "mode": "strict",
  "timeline": [
    {
      "event_id": "evt_001",
      "event_family": "market",
      "event_type": "FeatureSetBuilt",
      "event_time": "2026-07-06T10:00:00Z",
      "processing_time": "2026-07-06T10:00:00.100Z",
      "correlation_id": "cycle_btc_1h_xxx",
      "causation_id": "evt_000"
    }
  ],
  "families_present": ["market", "signal", "decision"],
  "causal_graph": {
    "nodes": [],
    "edges": [],
    "roots": []
  },
  "decision_diff": null,
  "feature_drift": null
}
```

With `mode=re_execute`, `decision_diff` and `feature_drift` are populated when applicable.

### GET `/replay/cycle/{correlation_id}/graph`

Causal graph only (`nodes`, `edges`, `roots`).

### POST `/replay/cycle/{correlation_id}`

Same query params and response as timeline.

---

## Experiments & config

[governance.md](../architecture/governance.md)

### GET `/experiments`

Query: `limit=50`.

### POST `/experiments`

```json
{
  "name": "baseline_june",
  "revision_id": null,
  "mode": "validation",
  "description": "",
  "hypothesis": null,
  "symbols": ["BTC/USDT"],
  "timeframes": ["1h"]
}
```

If `revision_id` is omitted, current config revision is created automatically.

### GET `/experiments/{experiment_id}`

Experiment record with `experiment_id`, `revision_id`, `status`, `symbols`, `timeframes`.

### GET `/config/revisions`

List of `ConfigRevision` records (hash lineage).

### GET `/config/revisions/{revision_id}`

Full revision including `config_bundle` and hashes.

---

## Analytics

### GET `/analytics/overview`

Query: `period=7d|30d|90d|365d`

See implementation response in [Phase 8 roadmap](../development/roadmap.md) — includes `rejection_trends`, `provider_contribution`, `by_symbol`, `outcome_summary`.

### GET `/analytics/heatmap`

Query: `period=30d` — approval rate by UTC hour and weekday.

```json
{
  "period": "30d",
  "data": [
    { "hour": 9, "day": "Monday", "win_rate": 0.65, "trades": 12 }
  ]
}
```

---

## Observability

### GET `/health`

```json
{
  "status": "ok",
  "phase": "8-production-mvp",
  "environment": "development",
  "app": "Quantitative Trading Platform",
  "default_symbol": "BTC/USDT",
  "default_timeframe": "1h",
  "symbols": ["BTC/USDT"],
  "timeframes": ["1h"]
}
```

### GET `/metrics`

Prometheus text format. Counters:

- `qtp_decisions_total{result=...}`
- `qtp_validation_runs_total{status=...}`
- `qtp_live_cycles_total{mode=...}`

Optional stack: `docker compose --profile observability up -d` (Prometheus `:9090`, Grafana `:3001`).

---

## Errors

FastAPI default shape:

```json
{ "detail": "Decision not found" }
```

Common status codes: `400`, `401`, `403`, `404`, `422`, `500`.
