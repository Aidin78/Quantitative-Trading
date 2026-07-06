# صفحات داشبورد

## 1. Overview (`/`)

صفحه اصلی — نمای کلی وضعیت سیستم.

### بخش‌ها

| بخش | محتوا |
|-----|--------|
| **Header Status** | وضعیت لایو (● Live / ○ Paused)، قیمت فعلی symbol پیش‌فرض، آخرین سیگنال |
| **KPI Cards** | Signals Today، Win Rate (30d)، Profit (30d)، Max Drawdown، Active Strategies |
| **Equity Curve** | نمودار 30 روز اخیر |
| **Recent Signals** | 10 سیگنال آخر — feed زنده |
| **Strategy Performance** | bar chart عملکرد هر استراتژی |
| **Market Conditions** | trend، volatility، session فعلی |

### Wireframe

```
┌─────────────────────────────────────────────────────────────────┐
│ [● Live]  BTC/USDT  $67,420  +1.2%     Last signal: 12m ago    │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ Signals  │ Win Rate │ Profit   │ Max DD   │ Active Strategies  │
│ Today: 3 │  62.4%   │ +4.2%    │ -8.1%    │ 5 / 7              │
├──────────┴──────────┴──────────┴──────────┴─────────────────────┤
│  Equity Curve (30d)              │  Recent Signals              │
│  ┌────────────────────────────┐  │  🟢 BUY BTC  78%  12:04      │
│  │                            │  │  🔴 SELL ETH 71%  09:31      │
│  │      [chart area]          │  │  🟢 BUY BTC  65%  yesterday  │
│  │                            │  │  ...                         │
│  └────────────────────────────┘  │                              │
├──────────────────────────────────┼──────────────────────────────┤
│  Strategy Performance            │  Market Conditions           │
│  [EMA ████████ 62%]              │  Trend: ↑ Uptrend            │
│  [RSI  ██████ 58%]               │  Volatility: Normal          │
│  [MACD ████ 45%]                 │  Session: Europe             │
└──────────────────────────────────┴──────────────────────────────┘
```

---

## 2. Signals (`/signals`)

### لیست سیگنال‌ها

**جدول:**

| ستون | توضیح |
|------|--------|
| Time | زمان صدور |
| Symbol | نماد |
| Side | BUY / SELL badge |
| Entry | قیمت ورود |
| SL | حد ضرر |
| TP | حد سود |
| Confidence | progress bar یا درصد |
| Strategies | تگ استراتژی‌های تأییدکننده |
| Status | sent / rejected / paper |

**فیلترها:**
- بازه تاریخ
- Symbol
- Side (BUY/SELL/All)
- Min confidence slider
- Strategy dropdown
- Status

**عملیات:**
- Export CSV
- کلیک روی ردیف → جزئیات

### جزئیات سیگنال (`/signals/[id]`)

| بخش | محتوا |
|-----|--------|
| **Signal Card** | تمام فیلدهای FinalSignal |
| **Candlestick Chart** | کندل با markers: entry (▲), SL (—), TP (—) |
| **Contributing Strategies** | جدول StrategySignal هر استراتژی + metadata |
| **Decision Log** | مراحل فیلتر → aggregate → risk |
| **Outcome** (اگر بسته شده) | PnL، exit reason، duration |

---

## 3. Strategies (`/strategies`)

### لیست

کارت برای هر استراتژی:

```
┌─────────────────────────────────────┐
│ EMA Crossover            [ON/OFF]  │
│ Win Rate: 58%  |  Signals: 142     │
│ Avg Confidence: 0.71               │
│ Last signal: 2h ago                │
│ [View Details]  [Configure]        │
└─────────────────────────────────────┘
```

### جزئیات (`/strategies/[id]`)

| بخش | محتوا |
|-----|--------|
| **Overview** | توضیح استراتژی، وضعیت، weight |
| **Parameters Form** | ویرایش پارامترها (RSI period, EMA fast/slow, ...) |
| **Performance Chart** | عملکرد در بازه‌های 7d / 30d / 90d |
| **Signal History** | سیگنال‌های تولیدشده توسط این استراتژی |
| **Analysis Log** | آخرین 50 تحلیل (شامل HOLD) |

---

## 4. Backtest (`/backtest`)

### فرم اجرا

| فیلد | نوع |
|------|-----|
| Symbol | select |
| Timeframe | select |
| Start Date | date picker |
| End Date | date picker |
| Initial Capital | number |
| Strategies | multi-select checkbox |
| Commission % | number |
| Slippage % | number |

دکمه: **Run Backtest**

### Progress (حین اجرا)

- Progress bar (0–100%)
- Log stream: «Processing 2024-03-15... 450/8760 candles»
- WebSocket: `/ws/backtest/{id}`

### نتایج (`/backtest/results/[id]`)

| بخش | محتوا |
|-----|--------|
| **KPI Row** | Win Rate، Profit Factor، Sharpe، Max DD، Total Trades، Net Profit |
| **Equity Curve** | نمودار سرمایه |
| **Drawdown Chart** | نمودار افت سرمایه |
| **Monthly Returns** | heatmap یا bar chart |
| **Trade Table** | تمام معاملات — sortable |
| **Per-Strategy Breakdown** | عملکرد تفکیکی |
| **Config Summary** | پارامترهای استفاده‌شده |
| **Actions** | Export PDF، Compare، Re-run |

### مقایسه بک‌تست‌ها

انتخاب 2–3 بک‌تست → overlay equity curves

---

## 5. Live Monitor (`/live`)

| بخش | محتوا |
|-----|--------|
| **System Status** | connected، exchange latency، last candle time |
| **Controls** | Start / Stop / Pause، Mode: paper \| live |
| **Live Chart** | کندل real-time + سیگنال markers |
| **Signal Feed** | استریم WebSocket |
| **Decision Log** | آخرین 20 تصمیم (شامل rejected) |
| **Active Jobs** | symbol، timeframe، next run |

### Decision Log Entry

```
10:30:01  BTC/USDT 1h
  ├─ EMA Cross: BUY (0.75)
  ├─ RSI Div: BUY (0.68)
  ├─ Market Filter: ✓ PASS
  ├─ Aggregation: BUY consensus (0.72)
  ├─ Risk Check: ✗ FAIL — daily_drawdown_limit
  └─ Result: REJECTED
```

---

## 6. Analytics (`/analytics`)

| بخش | محتوا |
|-----|--------|
| **Period Selector** | 7d / 30d / 90d / 1y / custom |
| **Performance Summary** | KPIهای دوره |
| **Equity Curve** | با benchmark (buy & hold) |
| **PnL Distribution** | histogram |
| **By Symbol** | جدول عملکرد per symbol |
| **By Strategy** | جدول + chart |
| **By Time** | heatmap ساعت × روز هفته |
| **R:R Analysis** | planned vs actual |
| **Walk-Forward Results** | اگر اجرا شده |

---

## 7. Risk (`/risk`)

| بخش | محتوا |
|-----|--------|
| **Active Rules** | لیست قوانین با مقدار فعلی |
| **Gauges** | daily drawdown vs limit، signals today vs max |
| **Rejected Signals** | سیگنال‌های ردشده به‌خاطر ریسک |
| **Edit Rules** | فرم ویرایش risk.yaml (با confirm) |

### Risk Gauge Example

```
Daily Drawdown
[████████░░░░░░░░░░░░] 2.1% / 5.0%

Signals Today
[██████░░░░░░░░░░░░░░] 3 / 10
```

---

## 8. Settings (`/settings`)

### تب‌ها

| تب | محتوا |
|----|--------|
| **General** | timezone، default symbol، theme |
| **Telegram** | bot token، channel ID، test send |
| **Exchange** | API key/secret (masked)، test connection |
| **Notifications** | enable/disable، format |
| **Users** | (اگر multi-user) مدیریت کاربران |

---

## Responsive Behavior

| صفحه | Desktop | Tablet | Mobile |
|------|---------|--------|--------|
| Overview | full grid | 2-col | stacked |
| Signals table | all columns | hide metadata | card view |
| Charts | side-by-side | stacked | full width |
| Live | chart + feed | stacked | feed only |
| Sidebar | fixed | collapsible | drawer |

---

## Loading & Empty States

| حالت | UI |
|------|-----|
| Loading | skeleton cards + table rows |
| No signals | illustration + «No signals yet» |
| Backtest running | progress + cancel button |
| API error | toast + retry button |
| WS disconnected | badge «Reconnecting...» in header |
