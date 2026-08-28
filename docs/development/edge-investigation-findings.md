# بررسی ریشه‌ای: چرا provider سودده پیدا نمی‌شد

این سند نتیجه‌ی یک بررسی کامل کد پلتفرم است که برای پاسخ به این سؤال انجام شد: چرا هیچ‌کدام از Signal Providerهای موجود (EMA, MACD, RSI, ADX, BB, SuperTrend, Volume, Market Structure) روی BTC/USDT در تایم‌فریم 1h نتیجه‌ی پایدار (train/test/holdout هم‌سو) تولید نمی‌کردند.

چهار مشکل پیدا شد — همه اکنون فیکس‌شده‌اند: **دو باگ فنی قطعی** (کالیبراسیون confidence، تعریف crossover)، **یک باگ متدولوژیک مهم** (look-ahead bias در fill price)، و **یک شکاف در مدیریت ریسک زنده** (`daily_drawdown_pct`).

**نتیجه‌ی نهایی (بعد از فیکس همه‌ی موارد بحرانی):** هیچ‌کدام از EMA solo، BB solo، یا ترکیب EMA+BB روی BTC/USDT در تایم‌فریم 1h ادج آماری پایدار ندارند — نتایج قبلی که ادج مثبت نشان می‌دادند صرفاً محصول باگ‌های فنی (۱ و ۲) و بایاس نگاه‌به‌جلو (۳) بودند، نه یک الگوی واقعی بازار. این نتیجه با تحقیق مستقل و عمیق‌تر در [candidate-stability-findings.md](./candidate-stability-findings.md) تأیید و تکمیل شد — از جمله رد شدن ensemble، تایم‌فریم بزرگ‌تر، و سیگنال‌های با فرضیه‌ی متفاوت (order-flow)، به‌همراه تأیید مستقیم که علت ریشه‌ای یک باگ زیرساختی نیست بلکه کوچک بودن gross edge نسبت به هزینه‌ی معامله است.

---

## ✅ فیکس‌شده

### 1. فرمول confidence در EMA/MACD/BB هرگز به آستانه‌ی خودش نمی‌رسید

**فایل‌ها:** [ema_crossover.py](../../backend/src/providers/ema_crossover.py), [macd_momentum.py](../../backend/src/providers/macd_momentum.py), [bollinger_reversion.py](../../backend/src/providers/bollinger_reversion.py)

هر provider یک فرمول `confidence = clamp(0.55 + ضریب × نسبت‌به‌ATR, 0.55, 0.95)` دارد. مشکل: نسبت‌های واقعی (`spread/ATR`, `histogram/ATR`, `penetration`) روی داده‌ی واقعی BTC/USDT خیلی کوچیک‌تر از چیزی بودند که ضرایب انتخاب‌شده فرض کرده بودند. نتیجه: سقف عملی confidence این providerها (۰.۵۸–۰.۶۴) زیر `min_confidence` تنظیم‌شده (۰.۶–۰.۶۵) می‌ماند — یعنی provider تقریباً همیشه HOLD می‌داد، مستقل از کیفیت واقعی سیگنال.

**تأیید شده روی ۶ ماه داده‌ی واقعی 1h (٪ سیگنال‌های عبوری از آستانه):**

| Provider | قبل | بعد |
|---|---|---|
| EMA crossover | ۰٪ (۰ از ۴۳۴۳) | ۸۷٪ (۳۷۹۶ از ۴۳۴۳) |
| MACD momentum | ۰٪ (۰ از ۲۲۷۰) | ۷۰٪ (۱۵۸۰ از ۲۲۷۰) |
| Bollinger reversion | ۴۰٪ (۲۰۲ از ۵۱۲) | ۷۳٪ (۳۷۶ از ۵۱۲) |

**تست‌ها:** ۵۱ تست unit مربوط به providerها پاس. تست‌های synthetic قبلی (`context.atr=335` ثابت) این باگ را پوشش نمی‌دادند چون spread تست ۶ برابر ATR بود — خیلی بزرگ‌تر از رفتار واقعی بازار.

### 2. `ema_cross_bullish`/`ema_cross_bearish` یک state پیوسته بود، نه یک رویداد تقاطع

**فایل‌ها:** [config/features.yaml](../../config/features.yaml), [ema_cross.py](../../backend/src/features/indicators/ema_cross.py) (جدید), [constant.py](../../backend/src/features/indicators/constant.py) (جدید)

تعریف قبلی flag: `ema_12 > ema_26` — این یک **وضعیت** است، نه یک رویداد. یعنی هر بار که EMA سریع بالای EMA کند بود (که تقریباً همیشه یک‌طرفه است در یک روند)، flag به‌طور پیوسته true می‌ماند، نه فقط لحظه‌ی تقاطع. روی داده واقعی: **۹۹.۹۸٪ باره‌ها** این flag فعال بود.

Provider اسمش `EmaCrossoverProvider` است ولی عملاً یک فیلتر روند پیوسته بود که هزاران سیگنال تکراری وسط یک روند تولید می‌کرد — نه سیگنال ورود در لحظه‌ی معتبر تقاطع. این با نتایج ضعیف win-rate (۳۲–۴۳٪) هم‌خوانی داشت چون entry معمولاً وسط یک روند already-established بود.

**فیکس:** یک indicator جدید (`ema_cross`) اضافه شد که فقط رویداد واقعی تقاطع (تغییر علامت spread نسبت به بار قبل) را برمی‌گرداند (+۱/-۱/۰)؛ flagها به `ema_cross > zero` / `ema_cross < zero` تغییر کردند (یک indicator کمکی `constant` هم برای مقایسه با صفر لازم بود چون flag-DSL فقط بین دو indicator مقایسه می‌کند). `features.yaml` از `v1` به `v2` ارتقا یافت چون معنای semantic فیچر عوض شده (اصل Feature Store: replay بدون drift).

**تأیید شده:** رویدادهای واقعی تقاطع فقط **۳.۵۵٪** باره‌ها هستند (۱۵۴ از ۴۳۴۴) — یعنی حالا رفتار Provider واقعاً با اسمش (crossover) مطابقت دارد.

**تست‌ها:** ۳۲۷ تست پاس (بدون تغییر نسبت به قبل از فیکس)، ۴ تست integration که از قبل و بدون ربط به این تغییرات fail می‌شدند (تأیید شد با git stash که با/بدون این فیکس یکسان fail می‌شوند).

### 3. Look-ahead bias در قیمت پرشدن معامله

**فایل‌ها:** [config/settings.yaml](../../config/settings.yaml), [execution/config.py:21](../../backend/src/execution/config.py#L21), [execution/simulated.py:243](../../backend/src/execution/simulated.py#L243), [execution/simulated_pending.py](../../backend/src/execution/simulated_pending.py), [execution/simulated_pricing.py:11-28](../../backend/src/execution/simulated_pricing.py#L11-L28), [runtime/platform_runtime.py](../../backend/src/runtime/platform_runtime.py)

> این بخش قبلاً «⏳ در انتظار تصمیم» علامت‌گذاری شده بود. بررسی مجدد (۲۰۲۶-۰۸-۲۵) نشان داد فیکس از قبل commit شده بود (کامیت `1168473`، هم‌زمان با نگارش اولیه‌ی همین سند) و کاملاً کار می‌کند؛ فقط جدول جمع‌بندی سند به‌روزرسانی نشده بود — همان الگویی که برای مورد #۴ (`daily_drawdown_pct`) هم رخ داده بود.

مدل fill پیش‌فرض قبلی (`close_price_v1`, `fill_at: close`) این‌طور کار می‌کرد:

1. Provider اندیکاتورها (EMA, RSI, ...) را از `close` **همان کندلی** که در حال پردازش است محاسبه می‌کند و سیگنال می‌دهد
2. `entry_price` هم برابر همان `close` است
3. معامله هم **دقیقاً همان‌جا** (با فقط ۵bps slippage) پر می‌شد

در دنیای واقعی این ممکن نیست: تا کندل کامل نبسته `close`اش را نمی‌دانید، و تا آن لحظه دیگر نمی‌توانید با همان قیمت وارد شوید.

**راه‌حل واقعی که پیاده و تأیید شده:**
- `config/settings.yaml`: `fill_models.default: next_open_v1` (همان slippage=5bps/fee=10bps مدل قبلی، فقط `fill_at: next_open`) — `load_default_fill_model()` این را واقعاً می‌خواند.
- `execution/simulated.py:243` — وقتی `fill_model.fill_at == "next_open"`، سفارش بلافاصله fill نمی‌شود؛ به‌جای آن یک `PendingEntry` صف می‌شود (`_pending_entries`).
- `execution/simulated_pending.py::process_pending_entries` — در ابتدای **cycle بعدی**، با `bar` جدید (کندل بعد از سیگنال) صدا زده می‌شود.
- `execution/simulated_pricing.py::fill_price` — وقتی `fill_at == "next_open"`، `base = bar["open"]` (نه `close`) است؛ این چک مستقل از پارامتر `use_next_open` هم برقرار است (`if use_next_open or engine._fill_model.fill_at == "next_open"`).
- `runtime/platform_runtime.py::run_cycle` → `evaluate_bar` (pre-decision، step 1 طبق docstring کلاس) هر cycle را با پردازش pending entries شروع می‌کند — یعنی سیگنال از `close[t]` صادر می‌شود و fill واقعاً روی `open[t+1]` رخ می‌دهد، دقیقاً طبق طراحی مستندشده در docstring `PlatformRuntime`.

**پوشش تست:** `test_next_open_defers_fill_to_next_bar` (تأیید صف‌شدن و fill روی کندل بعد) + کل `tests/unit/execution/` (۱۱ تست، همه pass). هیچ فایلی اشاره‌ای به `close_price_v1` به‌عنوان پیش‌فرض واقعی ندارد (فقط یک fallback مرده در `execution/config.py:44` برای زمانی که کلید `default` در YAML وجود نداشته باشد، که نیست).

---

## ✅ فیکس‌شده (به‌روزرسانی)

### 4. `daily_drawdown_pct` هرگز محاسبه نمی‌شد — چک risk مربوطه عملاً بی‌اثر بود

**فایل‌ها:** [core/contracts/state.py](../../backend/src/core/contracts/state.py), [state/store.py](../../backend/src/state/store.py), [runtime/platform_runtime.py](../../backend/src/runtime/platform_runtime.py), [engine/risk_manager.py:19-29](../../backend/src/engine/risk_manager.py#L19-L29)

> این بخش قبلاً «هنوز فیکس نشده» علامت‌گذاری شده بود. بررسی مجدد (۲۰۲۶-۰۸-۲۵) نشان داد فیکس واقعی از قبل در دو کامیت روی `main` انجام شده بود: `57d45c8` («Add daily_start_equity to RiskState and update drawdown calculations in InMemoryStateStore») و `6d3301d` («fix: address code review findings on live/backtest parity, risk, and reliability»). فقط این سند به‌روزرسانی نشده بود.

`RiskManager.evaluate` چک `risk.daily_drawdown_pct < max_daily_drawdown_pct` (پیش‌فرض ۵٪) را دارد که معاملات جدید را وقتی ضرر روزانه از حد مجاز عبور کرد مسدود می‌کند — این چک بدون تغییر باقی مانده و درست است.

**راه‌حل واقعی که پیاده شده:**
- `RiskState.daily_start_equity: float = 0.0` — فیلد جدید additive روی contract فریز‌شده ([core/contracts/state.py](../../backend/src/core/contracts/state.py))
- `state/store.py` در دو مسیر `daily_drawdown_pct` را محاسبه می‌کند: `_apply_position_closed` (بستن پوزیشن) و `_apply_mark_to_market` (revaluation لحظه‌ای پوزیشن‌های باز — چیزی که سند قبلی حتی اسمش را نبرده بود) — فرمول: `max(0.0, (start_equity - new_equity) / start_equity * 100)` با `start_equity = risk.daily_start_equity or new_equity`
- `runtime/platform_runtime.py` → `_maybe_reset_daily_risk` روی مرز روز، `daily_start_equity` را به equity فعلی ریست می‌کند (نه در `store.py` همان‌طور که حدس اولیه بود)

**پوشش تست:** مسیر واقعی state store (نه فقط mock fixture) از قبل در `backend/tests/unit/state/test_transitions.py` پوشش داده شده بود. یک شکاف باقی‌مانده — تست end-to-end که ضرر واقعی → snapshot → `RiskManager.evaluate` → رد سیگنال بعدی را زنجیره کند — در `backend/tests/unit/engine/test_risk_limits.py` اضافه شد (`test_real_state_store_loss_produces_working_daily_drawdown_circuit_breaker`؛ ضرر ۶٪ روی ۱۰٬۰۰۰$ equity → `rejection_reason == "daily_drawdown"` تأیید شد). ۴۶۶ تست پاس.

---

## بررسی‌شده و بدون مشکل

برای شفافیت، این بخش‌ها با دقت بررسی شدند و مشکلی پیدا نشد:

- **Data slicing (`csv_provider.py`)** — `get_latest(end=...)` درست فقط تا `end` را برمی‌گرداند؛ نشتی داده‌ی آینده وجود ندارد.
- **Train/test/holdout splits (`optimization_windows.py`, `walk_forward.py`)** — مرزها chronological و non-overlapping هستند.
- **Aggregator, RiskManager, FinalSignalBuilder, DecisionEngine** — منطق ترکیب سیگنال و مسیر تصمیم درست است.
- **Optimization scoring (`optimization_scoring.py`)** — به‌درستی train منفی را رد می‌کند، fold instability را پنالتی می‌کند.
- **ADX, SuperTrend, RSI, Volume, Market Structure providers** — فرمول‌های confidence‌شان از ابتدا به‌درستی کالیبره بودند (نیازی به فیکس نداشتند).

---

## جمع‌بندی وضعیت

| # | مشکل | severity | وضعیت |
|---|---|---|---|
| 1 | فرمول confidence EMA/MACD/BB کالیبره‌نشده | بحرانی | ✅ فیکس شد |
| 2 | تعریف اشتباه crossover (state به‌جای event) | بحرانی | ✅ فیکس شد |
| 3 | Look-ahead bias در fill price (`fill_at: close`) | بحرانی | ✅ فیکس شد (`1168473`) — تأیید شد ۲۰۲۶-۰۸-۲۵ |
| 4 | `daily_drawdown_pct` هرگز محاسبه نمی‌شد | متوسط (ریسک زنده، نه بک‌تست) | ✅ فیکس شد (`57d45c8`, `6d3301d`) — تست end-to-end تکمیل شد ۲۰۲۶-۰۸-۲۵ |

**نکته‌ی مهم (به‌روزرسانی ۲۰۲۶-۰۸-۲۵):** این نگرانی — که هیچ‌کدام از استراتژی‌های موجود به‌تنهایی روی BTC/USDT در 1h ادج آماری پایدار نداشته باشند چون بازار به‌شدت رقابتی است — با تحقیق مستقل و مفصل در [candidate-stability-findings.md](./candidate-stability-findings.md) به‌طور کامل بررسی شد: چهار مسیر (تنظیم آستانه، ترکیب چند provider هم‌راستا، تایم‌فریم بزرگ‌تر ۴h/1d، و سیگنال با فرضیه‌ی متفاوت مثل order-flow) همگی تست و رد شدند. بررسی زیرساخت در همان سند نشان داد این نتیجه یک یافته‌ی آماری واقعی است، نه باگ: gross edge سیگنال‌های کلاسیک روی این بازار/تایم‌فریم به‌قدری کوچک است که هزینه‌ی واقعی معامله (fee+slippage، حدود ۰.۳٪ رفت‌وبرگشت) آن را می‌بلعد.
