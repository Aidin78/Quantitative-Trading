# صفحات داشبورد

## 1. Decision Monitor (`/`)

صفحه اصلی — مشاهده زنده تصمیم‌های Engine. این صفحه باید قبل از Signals و Providers ساخته شود.

### بخش‌ها

| بخش | محتوا |
|-----|--------|
| **Runtime Status** | live/paper/paused، آخرین cycle، latency |
| **Decision Feed** | همه decisionها: approved + rejected |
| **Rejection Breakdown** | دلایل رد: risk، filter، low confidence |
| **Feature Snapshot** | `FeatureSet` آخرین cycle: RSI، EMA، ATR، flags |
| **Provider Votes** | خروجی هر SignalProvider برای decision انتخاب‌شده |
| **Engine Config Summary** | aggregation، risk، market filter |

### Wireframe

```
┌─────────────────────────────────────────────────────────────────┐
│ [● Live]  BTC/USDT  Last cycle: 10:30:01  Latency: 240ms       │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ Decisions│ Approval │ Rejected │ Max DD   │ Active Providers   │
│ Today:48 │  18.4%   │  81.6%   │ -8.1%    │ 5 / 7              │
├──────────┴──────────┴──────────┴──────────┴─────────────────────┤
│  Rejection Breakdown             │  Decision Feed               │
│  ┌────────────────────────────┐  │  🟢 BUY BTC  78%  12:04      │
│  │ risk ███████               │  │  ⚪ REJECT BTC risk 11:00    │
│  │ filter ████                │  │  ⚪ REJECT ETH low conf      │
│  │                            │  │  ...                         │
│  └────────────────────────────┘  │                              │
├──────────────────────────────────┼──────────────────────────────┤
│  Feature Snapshot                │  Provider Votes              │
│  RSI14: 28.5  ATR: 450           │  EMA: BUY 0.75               │
│  EMA cross bullish: true         │  RSI: BUY 0.68               │
│  Trend: ↑ Uptrend                │  MACD: HOLD                  │
└──────────────────────────────────┴──────────────────────────────┘
```

---

## 2. Engine Config (`/engine`)

| بخش | محتوا |
|-----|--------|
| **Aggregation** | method، min_agreeing_providers |
| **Market Filter** | sessions، min_atr_pct |
| **Risk Rules** | drawdown، confidence، max positions |
| **Revision** | `revision_id` فعال + lineage |

ویرایش از `PATCH /api/v1/engine/config` — هر تغییر → `ConfigRevision` جدید.

---

## 3. Forensic / Replay (`/replay`)

صفحه تحلیل علت تصمیم — [replay-engine.md](../architecture/replay-engine.md).

| بخش | محتوا |
|-----|--------|
| **Cycle Search** | جستجو با `correlation_id` یا بازه زمانی |
| **Timeline** | chain کامل Market → Signal → Decision → Execution |
| **Causal Graph** | گراف علت برای decision انتخاب‌شده |
| **Decision Diff** | مقایسه recorded vs re-executed (فاز 8) |

### Wireframe

```
┌─────────────────────────────────────────────────────────────────┐
│ Replay: cycle_btc_1h_20260706_1000                              │
├──────────────────────────────┬──────────────────────────────────┤
│ Timeline                     │ Causal Graph                     │
│ 10:00 FeatureSetBuilt        │  FeatureSetBuilt                 │
│ 10:00 ProviderOpinion ×2     │       ├─► ProviderOpinion        │
│ 10:00 DecisionRejected       │       └─► DecisionRejected       │
│       (risk: drawdown)       │            (risk_manager)        │
└──────────────────────────────┴──────────────────────────────────┘
```

---

## 4. Experiments (`/experiments`)

Governance — [governance.md](../architecture/governance.md).

| بخش | محتوا |
|-----|--------|
| **Experiment List** | name، revision، status، آخرین metrics |
| **Create** | انتخاب revision + symbols + hypothesis |
| **Compare** | side-by-side دو experiment |
| **Drill-down** | لینک به decisions/replay per cycle |

---

## 5. Signals (`/signals`)

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
| Providers | تگ Providerهای مشارکت‌کننده |
| Status | sent / rejected / paper |

**فیلترها:**
- بازه تاریخ
- Symbol
- Side (BUY/SELL/All)
- Min confidence slider
- Provider dropdown
- Status

**عملیات:**
- Export CSV
- کلیک روی ردیف → جزئیات

### جزئیات سیگنال (`/signals/[id]`)

| بخش | محتوا |
|-----|--------|
| **Signal Card** | تمام فیلدهای FinalSignal |
| **Candlestick Chart** | کندل با markers: entry (▲), SL (—), TP (—) |
| **Contributing Providers** | جدول StrategySignal هر Provider + metadata |
| **Decision Log** | مراحل فیلتر → aggregate → risk |
| **Outcome** (اگر بسته شده) | PnL، exit reason، duration |

---

## 6. Providers (`/providers`)

### لیست

کارت برای هر SignalProvider:

```
┌─────────────────────────────────────┐
│ EMA Crossover Provider   [ON/OFF]  │
│ Win Rate: 58%  |  Signals: 142     │
│ Avg Confidence: 0.71               │
│ Last signal: 2h ago                │
│ [View Details]  [Configure]        │
└─────────────────────────────────────┘
```

### جزئیات (`/providers/[id]`)

| بخش | محتوا |
|-----|--------|
| **Overview** | توضیح Provider، وضعیت، weight |
| **Parameters Form** | تنظیمات تفسیر Provider؛ اندیکاتورها در Feature Config هستند |
| **Performance Chart** | عملکرد در بازه‌های 7d / 30d / 90d |
| **Signal History** | StrategySignalهای تولیدشده توسط این Provider |
| **Analysis Log** | آخرین 50 تحلیل (شامل HOLD) |

---

## 7. Validation (`/validation`)

### فرم اجرا

| فیلد | نوع |
|------|-----|
| Symbol | select |
| Timeframe | select |
| Start Date | date picker |
| End Date | date picker |
| Initial Capital | number |
| Providers | multi-select checkbox |
| Commission % | number |
| Slippage % | number |

دکمه: **Run Validation**

### Progress (حین اجرا)

- Progress bar (0–100%)
- Log stream: «Processing 2024-03-15... 450/8760 candles»
- WebSocket: `/ws/validation/{id}`

### نتایج (`/validation/results/[id]`)

| بخش | محتوا |
|-----|--------|
| **Engine KPI Row** | Approval Rate، Rejection Breakdown، Provider Contribution |
| **Outcome KPI Row** | Win Rate، Profit Factor، Sharpe، Max DD، Total Trades، Net Profit |
| **Equity Curve** | نمودار سرمایه |
| **Drawdown Chart** | نمودار افت سرمایه |
| **Monthly Returns** | heatmap یا bar chart |
| **Trade Table** | تمام معاملات — sortable |
| **Per-Provider Breakdown** | contribution و عملکرد تفکیکی |
| **Config Summary** | پارامترهای استفاده‌شده |
| **Actions** | Export PDF، Compare، Re-run |

### مقایسه بک‌تست‌ها

انتخاب 2–3 بک‌تست → overlay equity curves

---

## 8. Live Monitor (`/live`)

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

## 9. Analytics (`/analytics`)

| بخش | محتوا |
|-----|--------|
| **Period Selector** | 7d / 30d / 90d / 1y / custom |
| **Performance Summary** | KPIهای دوره |
| **Equity Curve** | با benchmark (buy & hold) |
| **PnL Distribution** | histogram |
| **By Symbol** | جدول عملکرد per symbol |
| **By Provider** | جدول + chart |
| **By Time** | heatmap ساعت × روز هفته |
| **R:R Analysis** | planned vs actual |
| **Walk-Forward Results** | اگر اجرا شده |

---

## 10. Risk (`/risk`)

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

## 11. Settings (`/settings`)

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
| Validation running | progress + cancel button |
| API error | toast + retry button |
| WS disconnected | badge «Reconnecting...» in header |
