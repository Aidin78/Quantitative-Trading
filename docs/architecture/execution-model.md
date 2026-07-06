# Execution Model — مدل اجرای رسمی

> Telegram و DB **خروجی** هستند، نه مدل اجرا. Execution Model lifecycle کامل «اثر تصمیم» را از تولید سفارش تا fill و به‌روزرسانی state تعریف می‌کند.
>
> مرتبط: [event-model.md](./event-model.md) | [state-management.md](./state-management.md) | [state-risk-contract.md](./state-risk-contract.md) | [replay-engine.md](./replay-engine.md)

## مشکل بدون Execution Model

| وضعیت فعلی | پیامد |
|------------|--------|
| `TradeSimulated` یک event پراکنده | replay نمی‌داند fill چطور محاسبه شد |
| Telegram = «اجرا» | اشتباه مفهومی — notification ≠ execution |
| PnL در handler جدا | state و execution از هم جدا می‌شوند |
| live بدون order lifecycle | غیرقابل audit |

## اصل طراحی

```
DecisionApproved  →  Execution Pipeline  →  StateTransition
                         │
                    نه sink مستقیم
```

**Execution Layer** مسئول تبدیل `FinalSignal` به `Order` → `Fill` → `Position` است. Handlerهای Telegram/DB فقط **مصرف‌کننده** `ExecutionEvent` هستند.

## Execution Pipeline

```
DecisionApproved
    │
    ▼
ExecutionEvent(OrderIntentCreated)      ← intent از FinalSignal
    │
    ▼
ExecutionEvent(OrderSubmitted)          ← validation: simulator / live: broker adapter
    │
    ├──► ExecutionEvent(OrderRejected)  ← risk pre-trade / broker reject
    │
    ▼
ExecutionEvent(OrderAcknowledged)     ← تأیید دریافت
    │
    ▼
ExecutionEvent(FillReceived)            ← partial یا full fill
    │
    ▼
ExecutionEvent(PositionOpened)          ← state transition trigger
    │
    ... (مدیریت position: SL/TP/timeout)
    │
    ▼
ExecutionEvent(FillReceived)            ← exit fill
    │
    ▼
ExecutionEvent(PositionClosed)
    │
    ▼
StateTransitionEvent(PositionClosed)    ← StateStore.apply_transition
```

### Notification (جدا از execution)

```
ExecutionEvent(PositionOpened)
    │
    └──► handler: SignalPublished → Telegram  (side-effect)
```

## مدل‌های دامنه

### OrderIntent

خروجی مستقیم `FinalSignal` — هنوز سفارش واقعی نیست.

```python
@dataclass(frozen=True)
class OrderIntent:
    intent_id: str
    decision_id: str
    correlation_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    order_type: Literal["MARKET", "LIMIT"]
    limit_price: float | None
    stop_loss: float
    take_profit: float
    state_snapshot_id: str           # snapshot قبل از execution
    experiment_id: str | None        # governance — [governance.md](./governance.md)
```

### Order

```python
@dataclass(frozen=True)
class Order:
    order_id: str
    intent_id: str
    status: Literal[
        "pending", "submitted", "acknowledged",
        "partially_filled", "filled", "cancelled", "rejected"
    ]
    submitted_at: datetime           # processing_time
    venue: Literal["simulator", "paper", "live"]
```

### Fill

```python
@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    price: float
    quantity: float
    fee: float
    slippage_bps: float
    fill_time: datetime              # event_time در simulation؛ exchange time در live
    is_partial: bool
```

## ExecutionEvent — taxonomy کامل

| event_type | trigger | payload کلیدی |
|------------|---------|---------------|
| `OrderIntentCreated` | DecisionApproved | `OrderIntent` |
| `OrderSubmitted` | executor.submit() | `order_id`, `venue` |
| `OrderAcknowledged` | broker/sim ack | `order_id` |
| `OrderRejected` | pre-trade risk / broker | `reason`, `stage` |
| `FillReceived` | simulator یا exchange | `Fill` |
| `PositionOpened` | first fill on entry | `position_id`, `entry_fill_id` |
| `PositionClosed` | exit fill complete | `position_id`, `exit_reason`, `pnl` |
| `SignalPublished` | notification handler | `channels` — **نه** execution |
| `ExecutionFailed` | unrecoverable error | `error`, `stage` |

## ExecutionEngine

```python
class ExecutionEngine(Protocol):
    async def execute(self, decision: Decision, snapshot: StateSnapshot) -> ExecutionResult: ...

class ExecutionResult:
    events: tuple[ExecutionEvent, ...]   # ordered — برای event_log
    final_state_transition: StateTransitionEvent | None
```

### پیاده‌سازی‌ها

| impl | venue | کاربرد |
|------|-------|--------|
| `SimulatedExecutionEngine` | `simulator` | Validation Harness |
| `PaperExecutionEngine` | `paper` | Live بدون پول واقعی |
| `BrokerExecutionEngine` | `live` | فاز آینده — ccxt/MT5 |

**قانون:** Validation Harness دیگر مستقیم `trade_simulator` صدا نمی‌زند؛ `ExecutionEngine` event تولید می‌کند و `StateStore` از `FillReceived` به‌روز می‌شود.

## Fill Simulation (Validation)

```python
@dataclass(frozen=True)
class FillModel:
    """قرارداد deterministic برای replay"""
    model_id: str                      # e.g. "close_price_v1"
    slippage_bps: float
    fee_bps: float
    fill_at: Literal["close", "next_open", "mid"]

class SimulatedExecutionEngine:
    def __init__(self, fill_model: FillModel, clock: Clock): ...
```

هر fill باید در `event_log` با `fill_model_id` ثبت شود تا re-execute replay همان نتیجه را بدهد.

## Pre-Trade vs Decision-Time Risk

| مرحله | مسئول | snapshot |
|-------|--------|----------|
| Decision-time | `RiskManager` در Engine | `state_snapshot_id` قبل از تصمیم |
| Pre-trade | `ExecutionRiskGate` | snapshot جدید — ممکن است state بین تصمیم و اجرا عوض شده باشد |

```python
class ExecutionRiskGate:
    def check(self, intent: OrderIntent, snapshot: StateSnapshot) -> RiskVerdict:
        """آخرین خط دفاع قبل از OrderSubmitted"""
```

جزئیات مرز State/Risk: [state-risk-contract.md](./state-risk-contract.md).

## Persistence

```sql
CREATE TABLE orders (
    order_id          UUID PRIMARY KEY,
    intent_id         UUID NOT NULL,
    decision_id       UUID NOT NULL,
    correlation_id    VARCHAR(64) NOT NULL,
    status            VARCHAR(30) NOT NULL,
    venue             VARCHAR(20) NOT NULL,
    payload           JSONB NOT NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE fills (
    fill_id           UUID PRIMARY KEY,
    order_id          UUID REFERENCES orders(order_id),
    price             NUMERIC NOT NULL,
    quantity          NUMERIC NOT NULL,
    fee               NUMERIC NOT NULL,
    slippage_bps      NUMERIC NOT NULL,
    fill_time         TIMESTAMPTZ NOT NULL,
    fill_model_id     VARCHAR(50),     -- validation only
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
```

## Replay و Forensic

Strict replay باید chain کامل را بازسازی کند:

```
DecisionApproved → OrderIntentCreated → FillReceived → PositionClosed
```

Re-execute replay می‌تواند `FillModel` را عوض کند و `ExecutionDiff` تولید کند (مشابه `DecisionDiff`).

## Anti-Patterns

| Anti-Pattern | درست |
|--------------|------|
| Telegram = trade executed | `SignalPublished` جدا از `FillReceived` |
| PnL در simulation_handler | `PositionClosed` → StateTransition |
| trade بدون order_id | همیشه Order → Fill → Position |
| fill بدون fill_model_id | deterministic replay غیرممکن |
