# بک‌تست (Backtesting)

## هدف

اعتبارسنجی استراتژی‌ها و قوانین Decision Engine روی داده تاریخی **قبل از** اتصال به بازار زنده.

## فرآیند

```
1. انتخاب symbol، timeframe، بازه تاریخ
2. Load CSV → DataFrame
3. Walk-forward یا full-period iteration
4. برای هر نقطه زمانی:
   a. ساخت MarketContext
   b. اجرای تمام استراتژی‌های فعال
   c. DecisionEngine.process()
   d. اگر سیگنال → شبیه‌سازی معامله تا TP/SL/timeout
5. محاسبه Metrics
6. ذخیره نتایج در DB
7. نمایش در Dashboard
```

## BacktestRunner

```python
class BacktestRunner:
    def __init__(
        self,
        data_provider: MarketDataProvider,
        strategies: list[BaseStrategy],
        engine: DecisionEngine,
        config: BacktestConfig,
    ): ...

    def run(self) -> BacktestResult:
        df = self.data_provider.get_ohlcv(...)
        portfolio = PortfolioState.initial(config.initial_capital)
        trades: list[Trade] = []

        for i in range(self.warmup_bars, len(df)):
            window = df.iloc[:i+1]
            context = build_market_context(window, ...)
            signals = [s.analyze(window, context) for s in self.strategies]
            final = self.engine.process(signals, context, portfolio)

            if final:
                trade = self._simulate_trade(final, df.iloc[i:])
                trades.append(trade)
                portfolio = self._update_portfolio(portfolio, trade)

        return BacktestResult(trades=trades, metrics=compute_metrics(trades))
```

## شبیه‌سازی معامله

برای هر `FinalSignal`:

1. **Entry** — قیمت close کندل سیگنال (یا open کندل بعد)
2. **Monitor** — iterate کندل‌های بعدی
3. **Exit** وقتی:
   - `low <= stop_loss` (برای BUY) → exit با SL
   - `high >= take_profit` (برای BUY) → exit با TP
   - سیگنال معکوس → exit با SIGNAL
   - `max_bars_in_trade` رسید → exit با TIMEOUT

## معیارهای عملکرد

### معیارهای اصلی

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

## BacktestConfig

```yaml
backtest:
  symbol: "BTC/USDT"
  timeframe: "1h"
  start_date: "2024-01-01"
  end_date: "2025-01-01"
  initial_capital: 10000
  commission_pct: 0.1          # کارمزد هر معامله
  slippage_pct: 0.05
  max_bars_in_trade: 48      # حداکثر کندل در معامله
  warmup_bars: 200           # قبل از شروع سیگنال
  strategies:
    - ema_crossover
    - rsi_divergence
```

## خروجی‌ها

### BacktestResult

```python
@dataclass
class BacktestResult:
    id: str
    config: BacktestConfig
    trades: list[Trade]
    metrics: BacktestMetrics
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
python scripts/run_backtest.py \
  --symbol BTC/USDT \
  --timeframe 1h \
  --start 2024-01-01 \
  --end 2025-01-01 \
  --output results/backtest_001.json
```

## API

```
POST /api/v1/backtest/run     → job_id (async)
GET  /api/v1/backtest/{id}    → status + metrics
GET  /api/v1/backtest/{id}/trades
WS   /ws/backtest/{id}        → progress events
```

## نکات مهم

1. **Look-ahead bias** — فقط از داده تا کندل فعلی استفاده شود
2. **Survivorship bias** — داده نمادهای حذف‌شده را در نظر بگیرید
3. **Commission & slippage** — همیشه در شبیه‌سازی لحاظ شوند
4. **Out-of-sample** — هرگز روی Test بهینه نکنید
5. **تعداد معاملات** — نمونه کم (< 30) نتیجه را غیرقابل اعتماد می‌کند
