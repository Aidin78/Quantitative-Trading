# Validation Harness (Backtesting)

## هدف

اعتبارسنجی **Decision Engine + Feature Builder + Platform Runtime** روی داده تاریخی **قبل از** اتصال به بازار زنده.

در این معماری، بک‌تست یک محصول مستقل نیست؛ یک `ValidationHarness` است که همان Runtime لایو را روی تاریخ اجرا می‌کند.

## فرآیند

```
1. انتخاب symbol، timeframe، بازه تاریخ
2. Load CSV → OHLCV window
3. FeatureBuilder → `FeatureSet` + `MarketContext`
4. SignalProviders → `StrategySignal[]`
5. DecisionEngine → `Decision` (approved/rejected)
6. اگر approved → `ExecutionEngine` (Simulated) → OrderIntent → Fill → PositionClosed
7. `StateStore.apply_transition` از روی `FillReceived`
8. محاسبه Engine Metrics + Outcome Metrics
9. ذخیره `DecisionRecord` + `event_log` + orders/fills

مستندات اجرا: [execution-model.md](../architecture/execution-model.md)
```

## ValidationHarness

```python
class ValidationHarness:
    def __init__(
        self,
        runtime: PlatformRuntime,
        event_bus: EventBus,
        config: ValidationConfig,
    ): ...

    async def run(self) -> ValidationResult:
        for point in self._iterate_history():
            decision = await self.runtime.run_cycle(
                symbol=config.symbol,
                timeframe=config.timeframe,
                as_of=point.timestamp,
            )
            # events از Runtime/ExecutionEngine منتشر می‌شوند — نه harness مستقیم

        return ValidationResult(
            engine_metrics=compute_engine_metrics(),
            outcome_metrics=compute_outcome_metrics(),
        )
```

## شبیه‌سازی معامله (ExecutionEngine)

شبیه‌سازی دیگر در `trade_simulator` مستقل نیست — `SimulatedExecutionEngine` با `FillModel` deterministic:

```python
fill_model = FillModel(
    model_id="close_price_v1",
    slippage_bps=5,
    fee_bps=10,
    fill_at="close",
)
execution_engine = SimulatedExecutionEngine(fill_model, clock)
```

برای هر `Decision` با `result = approved`:

1. **Entry** — قیمت close کندل سیگنال (یا open کندل بعد)
2. **Monitor** — iterate کندل‌های بعدی
3. **Exit** وقتی:
   - `low <= stop_loss` (برای BUY) → exit با SL
   - `high >= take_profit` (برای BUY) → exit با TP
   - سیگنال معکوس → exit با SIGNAL
   - `max_bars_in_trade` رسید → exit با TIMEOUT

## معیارهای عملکرد

### Engine Metrics

| معیار | فرمول | حداقل پیشنهادی |
|-------|--------|-----------------|
| **Approval Rate** | approved / all_decisions | وابسته به استراتژی |
| **Rejection Breakdown** | group by rejection_reason | باید قابل توضیح باشد |
| **Provider Contribution** | provider در چند decision نهایی نقش داشته | — |
| **Decision Latency** | زمان هر cycle | مناسب timeframe |

### Outcome Metrics

| معیار | فرمول | حداقل پیشنهادی |
|-------|--------|-----------------|
| **Win Rate** | wins / total_trades | > 55% |
| **Profit Factor** | gross_profit / gross_loss | > 1.5 |
| **Max Drawdown** | max(peak - trough) / peak | < 15% |
| **Sharpe Ratio** | mean(returns) / std(returns) × √252 | > 1.0 |
| **Total Trades** | count | > 100 |
| **Avg R:R** | avg(actual_reward / actual_risk) | > 1.5 |

### معیارهای تکمیلی

| معیار | توضیح |
|-------|--------|
| **Calmar Ratio** | annual_return / max_drawdown |
| **Sortino Ratio** | مانند Sharpe با downside deviation |
| **Expectancy** | (win_rate × avg_win) - (loss_rate × avg_loss) |
| **Max Consecutive Losses** | بیشترین باخت پیاپی |
| **Recovery Factor** | net_profit / max_drawdown |

## Walk-Forward Validation

جلوگیری از overfitting:

```
|-------- Train 70% --------|-- Test 30% --|
         optimize params          validate

یا rolling:

|-- Train --|-- Test --|
      |-- Train --|-- Test --|
            |-- Train --|-- Test --|
```

**قانون:** پارامترها فقط روی Train بهینه شوند؛ نتیجه نهایی روی Test گزارش شود.

## فرمت CSV ورودی

```csv
timestamp,open,high,low,close,volume
2024-01-01 00:00:00,42000.0,42500.0,41800.0,42300.0,1234.56
2024-01-01 01:00:00,42300.0,42600.0,42100.0,42450.0,987.65
```

- `timestamp` — ISO 8601 یا Unix
- قیمت‌ها — float
- `volume` — float
- مرتب‌سازی صعودی بر اساس زمان

## ValidationConfig

```yaml
validation:
  symbol: "BTC/USDT"
  timeframe: "1h"
  start_date: "2024-01-01"
  end_date: "2025-01-01"
  initial_capital: 10000
  commission_pct: 0.1          # کارمزد هر معامله
  slippage_pct: 0.05
  max_bars_in_trade: 48      # حداکثر کندل در معامله
  warmup_bars: 200           # قبل از شروع سیگنال
  providers:
    - ema_crossover
    - rsi_divergence
  experiment_id: null          # یا ID از [governance.md](../architecture/governance.md)
  revision_id: null            # ConfigRevision — برای reproducibility
  fill_model_id: close_price_v1
```

## خروجی‌ها

### ValidationResult

```python
@dataclass
class ValidationResult:
    id: str
    config: ValidationConfig
    decisions: list[DecisionRecord]
    trades: list[Trade]
    engine_metrics: EngineMetrics
    outcome_metrics: OutcomeMetrics
    equity_curve: list[tuple[datetime, float]]
    drawdown_curve: list[tuple[datetime, float]]
    created_at: datetime
```

### Report (Dashboard)

- KPI cards
- Equity curve chart
- Drawdown chart
- Trade table
- Monthly returns heatmap
- Per-strategy breakdown

## CLI

```bash
python scripts/run_validation.py \
  --symbol BTC/USDT \
  --timeframe 1h \
  --start 2024-01-01 \
  --end 2025-01-01 \
  --output results/validation_001.json
```

## API

```
POST /api/v1/validation/run     → job_id (async)
GET  /api/v1/validation/{id}    → status + engine/outcome metrics
GET  /api/v1/validation/{id}/decisions
GET  /api/v1/validation/{id}/trades
WS   /ws/validation/{id}        → progress events
```

## نکات مهم

1. **Look-ahead bias** — فقط از داده تا کندل فعلی استفاده شود
2. **Survivorship bias** — داده نمادهای حذف‌شده را در نظر بگیرید
3. **Commission & slippage** — همیشه در شبیه‌سازی لحاظ شوند
4. **Out-of-sample** — هرگز روی Test بهینه نکنید
5. **تعداد معاملات** — نمونه کم (< 30) نتیجه را غیرقابل اعتماد می‌کند
