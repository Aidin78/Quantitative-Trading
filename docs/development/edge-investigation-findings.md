# بررسی ریشه‌ای: چرا provider سودده پیدا نمی‌شد

این سند نتیجه‌ی یک بررسی کامل کد پلتفرم است که برای پاسخ به این سؤال انجام شد: چرا هیچ‌کدام از Signal Providerهای موجود (EMA, MACD, RSI, ADX, BB, SuperTrend, Volume, Market Structure) روی BTC/USDT در تایم‌فریم 1h نتیجه‌ی پایدار (train/test/holdout هم‌سو) تولید نمی‌کردند.

سه دسته مشکل پیدا شد: **باگ‌های فنی قطعی** (فیکس شده)، **یک باگ متدولوژیک مهم** (فیکس شده)، و **یک شکاف در مدیریت ریسک** (هنوز فیکس نشده).

**نتیجه‌ی نهایی (بعد از فیکس همه‌ی موارد بحرانی):** هیچ‌کدام از EMA solo، BB solo، یا ترکیب EMA+BB روی BTC/USDT در تایم‌فریم 1h ادج آماری پایدار ندارند — نتایج قبلی که ادج مثبت نشان می‌دادند صرفاً محصول باگ‌های فنی (۱ و ۲) و بایاس نگاه‌به‌جلو (۳) بودند، نه یک الگوی واقعی بازار. جزئیات کامل در بخش [نتیجه‌ی نهایی](#نتیجه‌ی-نهایی-scorecard) پایین سند.

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

**فایل‌ها:** [config/settings.yaml](../../config/settings.yaml), [execution/config.py:21](../../backend/src/execution/config.py#L21), [runtime/platform_runtime.py:66-68](../../backend/src/runtime/platform_runtime.py#L66-L68)

مدل fill پیش‌فرض قبلی (`close_price_v1`, `fill_at: close`) این‌طور کار می‌کرد:

1. Provider اندیکاتورها (EMA, RSI, ...) را از `close` **همان کندلی** که در حال پردازش است محاسبه می‌کند و سیگنال می‌دهد
2. `entry_price` هم برابر همان `close` است
3. معامله هم **دقیقاً همان‌جا** (با فقط ۵bps slippage) پر می‌شد

در دنیای واقعی این ممکن نیست: تا کندل کامل نبسته `close`اش را نمی‌دانید، و تا آن لحظه دیگر نمی‌توانید با همان قیمت وارد شوید. خود کد قابلیت `fill_at: next_open` (سیگنال از `close[t]`، fill روی `open[t+1]`) را از قبل داشت (`PendingEntry` mechanism، پوشش تست دارد در `test_next_open_defers_fill_to_next_bar`)، اما هیچ‌جا در `settings.yaml` به‌عنوان مدل تعریف یا پیش‌فرض نشده بود.

**فیکس:** یک مدل جدید `next_open_v1` (همان slippage/fee، ولی `fill_at: next_open`) در [config/settings.yaml](../../config/settings.yaml) اضافه شد و `default` به آن تغییر کرد. تست‌ها: ۳۲۷ پاس (بدون تغییر)، همان ۴ fail قبلی و بی‌ربط.

---

## ⚠️ پیدا شده، هنوز فیکس نشده — شکاف مدیریت ریسک (خارج از بحث backtest)

### 4. `daily_drawdown_pct` هرگز محاسبه نمی‌شود — چک risk مربوطه عملاً بی‌اثر است

**فایل‌ها:** [state/store.py](../../backend/src/state/store.py), [engine/risk_manager.py:19-29](../../backend/src/engine/risk_manager.py#L19-L29), [execution/simulated_positions.py](../../backend/src/execution/simulated_positions.py)

`RiskManager.evaluate` یک چک سخت‌گیرانه دارد: `risk.daily_drawdown_pct < max_daily_drawdown_pct` (پیش‌فرض ۵٪) که قرار است معاملات جدید را وقتی ضرر روزانه از حد مجاز عبور کرد مسدود کند.

اما `daily_drawdown_pct`:
- در `RiskState` مقدار پیش‌فرض `0.0` دارد
- هر روز توسط `_maybe_reset_daily_risk` صفر می‌شود
- **هیچ‌جا واقعاً محاسبه/افزایش داده نمی‌شود** — `close_position` (در `simulated_positions.py`) فقط `pnl` (مقدار مطلق) را در transition payload می‌گذارد، نه یک درصد drawdown

نتیجه: این چک همیشه `0.0 < 5.0` است — یعنی **هرگز فعال نمی‌شود**، مستقل از این‌که چقدر پول در یک روز از دست برود. `daily_pnl` (مقدار مطلق دلاری) درست آپدیت می‌شود، ولی `daily_drawdown_pct` (که همان چیزیه که RiskManager واقعاً چک می‌کند) نه.

هیچ تستی هم این محاسبه را پوشش نمی‌دهد — تنها جاهایی که `daily_drawdown_pct` در تست‌ها ظاهر می‌شود، fixtureهای mock هستند که مقدار را دستی ست می‌کنند، نه مسیر واقعی state store.

**این باگ روی نتایج بک‌تست مستقیماً اثر نمی‌گذارد (چون بک‌تست‌ها معمولاً به این حد ضرر روزانه نمی‌رسند)، ولی برای معاملات زنده یک circuit-breaker امنیتی مهم است که الان عملاً وجود ندارد.**

**پیشنهاد فیکس:** در `_apply_position_closed` (یا `_maybe_reset_daily_risk`)، `daily_drawdown_pct` باید از equity ابتدای روز نسبت به equity فعلی (یا نسبت به peak روز) محاسبه و به‌روزرسانی شود، مشابه الگوی `max_drawdown_pct` که در `metrics.py` (`compute_monthly_breakdown`) از قبل درست پیاده‌سازی شده.

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
| 3 | Look-ahead bias در fill price (`fill_at: close`) | بحرانی | ⏳ در انتظار تصمیم |
| 4 | `daily_drawdown_pct` هرگز محاسبه نمی‌شود | متوسط (ریسک زنده، نه بک‌تست) | ⏳ فیکس نشده |

**نکته‌ی مهم:** حتی بعد از فیکس ۱ و ۲، ممکن است هیچ‌کدام از استراتژی‌های موجود (EMA cross، BB touch، ...) به‌تنهایی روی BTC/USDT در 1h ادج آماری پایدار نداشته باشند — چون این بازار به‌شدت رقابتی است و استراتژی‌های کلاسیک معمولاً توسط بازیگران دیگر آربیتراژ می‌شوند. نتیجه‌ی scorecard در حال اجرا (با فیکس ۱+۲) این را روشن می‌کند؛ اگر بازهم نتیجه ضعیف بود، گام بعدی می‌تواند شامل تست تایم‌فریم‌های بزرگ‌تر (4h/1d)، ترکیب چند provider هم‌راستا، یا طراحی provider جدید مبتنی بر فرضیه‌ی متفاوت باشد.
