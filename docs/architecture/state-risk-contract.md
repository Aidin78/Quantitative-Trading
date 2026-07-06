# State–Risk Contract — قرارداد enforceable

> مرز دقیق مسئولیت `StateStore` و `RiskManager` در طول lifecycle تصمیم. بدون این قرارداد، determinism شکسته می‌شود.
>
> مرتبط: [state-management.md](./state-management.md) | [execution-model.md](./execution-model.md) | [explainability.md](./explainability.md)

## اصل طلایی

```
RiskManager  =  read-only روی StateStore  (در فاز تصمیم)
StateStore   =  تنها mutator وضعیت
Runtime      =  orchestrator — ترتیب را enforce می‌کند
```

هیچ ماژول دیگری — از جمله `RiskManager`، Provider، Handler — حق `mutate` مستقیم state ندارد.

## نقش‌ها

| نقش | مسئولیت | حق نوشتن state |
|-----|---------|----------------|
| `StateStore` | نگهداری، snapshot، transition | ✅ تنها نویسنده |
| `RiskManager` | ارزیابی ریسک روی snapshot | ❌ |
| `DecisionEngine` | pipeline تصمیم؛ RiskManager را صدا می‌زند | ❌ |
| `ExecutionEngine` | سفارش و fill | ❌ — فقط `StateTransitionEvent` پیشنهاد می‌دهد |
| `ExecutionRiskGate` | pre-trade check | ❌ |
| Event Handlers | side-effect (DB, WS, Telegram) | ❌ |

## Lifecycle تصمیم — فازبه‌فاز

### فاز ۱: Pre-Decision Snapshot (اجباری)

```
T1  StateStore.snapshot(portfolio_id)
        → StateSnapshot { snapshot_id, portfolio, risk, version }
```

- **خواننده:** Engine، RiskManager، Providers (فقط context بازار — نه state)
- **نویسنده:** هیچ‌کس
- **ثبت:** `state_snapshot_id` در تمام eventهای بعدی این cycle

### فاز ۲: Decision (read-only)

```
T2  DecisionEngine.process(signals, context, snapshot)
        │
        ├── MarketFilter   (بدون state)
        ├── Aggregator     (بدون state)
        └── RiskManager.evaluate(aggregated, snapshot)  ← READ ONLY
                → RiskVerdict { checks, risk_state_version }
```

**Enforcement:**

```python
class RiskManager:
  def evaluate(self, signal: AggregatedResult, snapshot: StateSnapshot) -> RiskVerdict:
      assert snapshot.portfolio.version == snapshot.risk.version  # یا explicit coupling rule
      # فقط خواندن snapshot.portfolio و snapshot.risk
      # ممنوع: self.state_store.apply_transition(...)
```

`RiskVerdict` باید `risk_state_version` از snapshot را echo کند — برای audit.

### فاز ۳: Decision Event (بدون تغییر state)

```
T3  DecisionEvent(DecisionApproved | DecisionRejected)
        payload: { state_snapshot_id, risk_state_version, decision_log }
```

- تأیید یا رد **هنوز** state را عوض نمی‌کند
- رد = پایان cycle — state بدون تغییر

### فاز ۴: Execution (پس از تأیید)

```
T4  ExecutionEngine.execute(decision, snapshot)
        → ExecutionEvent chain (OrderIntent → Fill → ...)
```

**نکته:** بین T3 و T4 ممکن است cycle دیگری state را عوض کرده باشد → **snapshot جدید** قبل از execution:

```
T4a  StateStore.snapshot()  → snapshot_exec_id
T4b  ExecutionRiskGate.check(intent, snapshot_exec)
T4c  اگر pass → OrderSubmitted ...
```

### فاز ۵: State Mutation (تنها پس از Fill)

```
T5  StateStore.apply_transition(
        StateTransitionEvent(
          type=PositionOpened,
          causation_event_id=FillReceived.event_id,
          snapshot_id_before=snapshot_exec_id,
          ...
        )
    ) → StateSnapshot v(N+1)
```

**قانون:** transition بدون `causation_event_id` از نوع Execution مردود است.

## جدول خواندن/نوشتن

| لحظه | RiskManager | StateStore | ExecutionEngine |
|------|-------------|------------|-----------------|
| قبل از تصمیم | — | `snapshot()` read | — |
| حین تصمیم | `evaluate()` read snapshot | — | — |
| بعد از DecisionApproved | — | — | `execute()` read snapshot |
| pre-trade | — | `snapshot()` read | `ExecutionRiskGate` read |
| بعد از Fill | — | `apply_transition()` write | emit events only |

## Determinism Checklist

برای reproduce کردن تصمیم در replay:

1. همان `state_snapshot_id` (یا همان portfolio/risk version)
2. همان `feature_set_id` + `feature_version`
3. همان engine config (`experiment_id` / config hash)
4. همان provider outputs

برای reproduce کردن **outcome** (PnL):

5. همان `fill_model_id`
6. همان chain `ExecutionEvent`

## خطاهای رایج (ممنوع)

| # | Anti-Pattern | چرا ممنوع |
|---|--------------|-----------|
| 1 | RiskManager مستقیم `daily_pnl` را کم/زیاد کند | state دو منبع حقیقت |
| 2 | Handler بعد از DecisionApproved position بسازد | بدون Order/Fill chain |
| 3 | Engine بدون snapshot تصمیم بگیرد | replay غیرممکن |
| 4 | دو snapshot در یک cycle بدون version bump | race در validation |
| 5 | Risk روی stale snapshot (version قدیمی) | تصمیم نادرست |

## Runtime Enforcement

`PlatformRuntime` ترتیب را با state machine داخلی enforce می‌کند:

```python
class CyclePhase(Enum):
    INIT = "init"
    SNAPSHOT_TAKEN = "snapshot_taken"
    FEATURES_BUILT = "features_built"
    SIGNALS_COLLECTED = "signals_collected"
    DECISION_MADE = "decision_made"
    EXECUTING = "executing"
    COMPLETED = "completed"

class PlatformRuntime:
    def _assert_phase(self, expected: CyclePhase) -> None:
        if self._phase != expected:
            raise InvalidCyclePhaseError(expected, self._phase)
```

مثال:

```python
async def run_cycle(self, ...):
    self._phase = CyclePhase.INIT
    snapshot = self.state_store.snapshot(portfolio_id)
    self._phase = CyclePhase.SNAPSHOT_TAKEN
    # ... features, providers ...
    decision = self.engine.process(..., snapshot=snapshot)
    self._phase = CyclePhase.DECISION_MADE
    if decision.result == "approved":
        await self.execution_engine.execute(decision, snapshot)
    self._phase = CyclePhase.COMPLETED
```

## RiskState مشتق از Portfolio

`RiskState` **مشتق** از `PortfolioState` + limits است — نه منبع مستقل حقیقت:

```
PortfolioState (source of truth for positions, pnl)
        │
        ▼
RiskDeriver.derive(portfolio, limits) → RiskState
        │
        ▼
StateSnapshot { portfolio, risk }  — atomically paired
```

هنگام `apply_transition`، هر دو با هم به‌روز می‌شوند — version مشترک یا coupled versions در snapshot.

## Audit Fields (اجباری در DecisionEvent)

```json
{
  "state_snapshot_id": "snap_001",
  "portfolio_version": 42,
  "risk_state_version": 42,
  "risk_verdict": {
    "passed": true,
    "checks": [...]
  }
}
```

## جمع‌بندی

```
خواندن  → RiskManager فقط در evaluate() روی snapshot
نوشتن   → فقط StateStore.apply_transition() پس از ExecutionEvent
ترتیب   → Runtime state machine enforce می‌کند
audit   → snapshot_id + versions در هر DecisionEvent
```
