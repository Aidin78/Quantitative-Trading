# State Management — مدیریت وضعیت مرکزی

> وضعیت‌های `PortfolioState`، `PositionState` و `RiskState` به‌صورت مدل‌های versioned و مستقل تعریف می‌شوند تا بازسازی deterministic در validation و live ممکن باشد.
>
> مرتبط: [event-model.md](./event-model.md) | [replay-engine.md](./replay-engine.md) | [time-semantics.md](./time-semantics.md)

## مشکل بدون State Layer

| بدون State مرکزی | پیامد |
|------------------|--------|
| وضعیت پراکنده در handlers | غیرقابل replay |
| snapshot ضمنی در memory | اختلاف backtest/live |
| Risk بدون context تاریخی | تصمیم غیرقابل توضیح |

## اصول طراحی

1. **Single Source of Truth** — `StateStore` تنها نقطه خواندن/نوشتن state
2. **Immutable snapshots** — هر تغییر = snapshot جدید با `version`
3. **Event-sourced transitions** — تغییر state همیشه با `StateTransitionEvent` همراه است
4. **Mode-aware** — state جدا برای `validation`، `live`، `replay`

## مدل‌های اصلی

### PositionState

```python
@dataclass(frozen=True)
class PositionState:
    position_id: str
    symbol: str
    side: Literal["LONG", "SHORT"]
    quantity: float
    entry_price: float
    entry_time: datetime          # event_time
    stop_loss: float | None
    take_profit: float | None
    unrealized_pnl: float
    status: Literal["open", "closed"]
```

### PortfolioState

```python
@dataclass(frozen=True)
class PortfolioState:
    portfolio_id: str
    mode: Literal["validation", "live", "paper", "replay"]
    cash: float
    equity: float
    open_positions: tuple[PositionState, ...]
    realized_pnl: float
    version: int
    as_of_event_time: datetime
    as_of_processing_time: datetime
```

### RiskState

```python
@dataclass(frozen=True)
class RiskState:
    risk_state_id: str
    portfolio_id: str
    daily_pnl: float
    daily_drawdown_pct: float
    open_exposure_pct: float
    consecutive_losses: int
    limits: RiskLimits
    breached_limits: tuple[str, ...]
    version: int
    as_of_event_time: datetime

@dataclass(frozen=True)
class RiskLimits:
    max_daily_drawdown_pct: float
    max_open_positions: int
    max_exposure_pct: float
    max_consecutive_losses: int
```

## StateStore

```python
class StateStore(Protocol):
    def get_portfolio(self, portfolio_id: str) -> PortfolioState: ...
    def get_risk(self, portfolio_id: str) -> RiskState: ...
    def snapshot(self, portfolio_id: str) -> StateSnapshot: ...
    def apply_transition(self, event: StateTransitionEvent) -> StateSnapshot: ...
```

### StateSnapshot

```python
@dataclass(frozen=True)
class StateSnapshot:
    snapshot_id: str
    portfolio: PortfolioState
    risk: RiskState
    version: int
    created_at: datetime
    correlation_id: str           # cycle که snapshot در آن گرفته شد
```

هر `DecisionEvent` باید `state_snapshot_id` قبل از تصمیم را نگه دارد.

## State Transition

```
DecisionApproved
    │
    ▼
StateTransitionEvent(PositionOpened)
    │
    ▼
PortfolioState v(N+1) + RiskState v(M+1)
    │
    ▼
StateSnapshot(snap_xxx)
```

| transition_type | trigger | تغییر |
|-----------------|---------|-------|
| `PositionOpened` | trade simulated/opened | portfolio + risk |
| `PositionClosed` | TP/SL/timeout | portfolio + risk |
| `RiskLimitUpdated` | config change | risk only |
| `DailyReset` | session boundary | risk counters |

## تعامل با Decision Engine و Risk

مرز دقیق خواندن/نوشتن و lifecycle فازبه‌فاز در [state-risk-contract.md](./state-risk-contract.md) — **enforceable** و اجباری برای determinism.

خلاصه:

```
T1  StateStore.snapshot()           → state_snapshot_id
T2  RiskManager.evaluate(snapshot)  → read-only
T3  DecisionEvent                   → بدون mutate
T4  ExecutionEngine + snapshot جدید → Order/Fill chain
T5  StateStore.apply_transition()   → تنها نقطه نوشتن
```

## Persistence

```sql
CREATE TABLE state_snapshots (
    snapshot_id       UUID PRIMARY KEY,
    portfolio_id      VARCHAR(64) NOT NULL,
    version           INT NOT NULL,
    correlation_id    VARCHAR(64),
    event_time        TIMESTAMPTZ NOT NULL,
    portfolio_json    JSONB NOT NULL,
    risk_json         JSONB NOT NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE state_transitions (
    transition_id     UUID PRIMARY KEY,
    snapshot_id_before UUID REFERENCES state_snapshots(snapshot_id),
    snapshot_id_after  UUID REFERENCES state_snapshots(snapshot_id),
    transition_type   VARCHAR(50) NOT NULL,
    causation_event_id UUID NOT NULL,
    payload           JSONB,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
```

## Determinism در Validation vs Live

| جنبه | validation | live |
|------|------------|------|
| StateStore impl | InMemoryStateStore | PostgresStateStore |
| seed | ثابت از config | همان قرارداد |
| clock | SimulatedClock | WallClock |
| transitions | از ExecutionEvent | از ExecutionEvent |

اگر `event_log` + `state_snapshots` + `feature_store` یکسان باشند، replay باید همان تصمیم‌ها را تولید کند.

## Anti-Patterns

| Anti-Pattern | درست |
|--------------|------|
| PnL فقط در handler محاسبه شود | `PortfolioState` مرکزی |
| risk check بدون snapshot | `state_snapshot_id` در DecisionEvent |
| state mutable global | immutable snapshots + version |
| validation state جدا از schema | همان مدل‌ها، impl متفاوت |
