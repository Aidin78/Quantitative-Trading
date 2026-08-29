# نقشهٔ اجرای زندهٔ leg کری بازیس

leg کری بک‌تست دارد (`src/carry/`) ولی اجرای زنده ندارد. پلتفرم فعلی spot تک-ابزاره است.
این سند کار باقی‌مانده را scope می‌کند. leg هستهٔ long از قبل live-ready است.

## چه چیزی لازم است

### ۱. دادهٔ بازار پرپ (`src/data/perp_provider.py`)
- polling نرخ funding زنده + قیمت mark پرپ (ccxt، `defaultType: future`)
- قرارداد: `PerpQuote(symbol, mark_price, index_price, funding_rate, next_funding_time)`
- کش‌شده مثل `market_cache`؛ در حالت live از WebSocket یا REST poll هر ~۱ دقیقه

### ۲. مدیر پوزیشن دلتا-خنثی (`src/carry/position_manager.py`)
- state: `spot_qty`, `perp_qty`, `entry_spot_px`, `entry_perp_px`, `accrued_funding`
- `net_delta = spot_qty * spot_px - perp_qty * perp_px` (باید ~۰ بماند)
- `rebalance_needed(band: float)` — وقتی `|net_delta| / notional > band` (پیش‌فرض ۲٪)
- `target_orders()` — سفارش‌های spot + perp برای بازگرداندن دلتا به صفر
- `should_hold(trailing_funding, min_threshold)` — گیت ورود/خروج
- accrual funding: در هر رویداد funding، `accrued += funding_rate * perp_notional * sign`

### ۳. اجرای دو-ابزاره (`src/carry/carry_executor.py`)
- باز کردن جفت: خرید spot + شورت پرپ هم‌اندازه (taker، تحمل slippage)
- بستن جفت: معکوس
- ری‌بالانس: فقط delta delta را معامله کن، نه کل پوزیشن
- safety gate: اگر یک leg پر شد ولی دیگری نه (اجرای ناقص) → فوراً هج کن یا ببند
- سقف‌ها: max notional، max leverage روی leg پرپ، halt روی basis غیرعادی

### ۴. runner زنده (`scripts/run_carry_live.py` یا ادغام در `PlatformRuntime`)
- گزینهٔ A (ساده‌تر): runner مستقل carry، جدا از موتور Engine-Centric — چون کری
  مکانیکی است و سیگنال جهت‌دار ندارد. با APScheduler هر ~۸ ساعت (پیش از settlement funding)
  چک: هلد؟ ری‌بالانس؟
- گزینهٔ B: `CarryProvider` + مسیر اجرای جدید در `ExecutionEngine` — با اصل Engine-Centric
  سازگارتر ولی چند هفته کار روی هر لایه + قراردادها. توصیه: گزینهٔ A اول.
- کتاب ترکیبی: تخصیص سرمایه ۷۰/۳۰ بین runner کری و استراتژی هستهٔ موجود در سطح حساب؛
  overlay هدف-نوسان روی مجموع (اسکریپت `run_blended_book_backtest` منطقش را دارد).

### ۵. reconciliation + مانیتورینگ
- هر چرخه: پوزیشن‌های واقعی صرافی را با state داخلی تطبیق بده
- متریک‌های Prometheus: `carry_net_delta`, `carry_accrued_funding`, `carry_leverage`, `basis_bps`
- هشدار Telegram روی: اجرای ناقص، basis > آستانه، نزدیک شدن به liquidation پرپ

## ریسک‌هایی که بک‌تست نمی‌گیرد (در live باید مدیریت شوند)
- **ریسک basis:** spread قیمت spot-perp در ورود/خروج و در استرس باز می‌شود
- **ریسک صرافی:** ورشکستگی/freeze برداشت (FTX نوامبر ۲۰۲۲) — کری روی چند صرافی توزیع شود
- **ADL / liquidation:** روی leg شورت پرپ در حرکت شارپ صعودی — اهرم پرپ محافظه‌کار (~۲–۳x)
- **فشردگی funding:** بازده از ۲۰۲۱ کم شده؛ overlay هدف-نوسان تا حدی جبران می‌کند

## تخمین کار
- گزینهٔ A (runner مستقل): ~۱–۲ هفته برای نسخهٔ اول paper، + ~۱ هفته سخت‌کاری live
- نیازمندی کاربر: انتخاب صرافی(ها)، API key، تصمیم testnet/live، حداقل سرمایه
