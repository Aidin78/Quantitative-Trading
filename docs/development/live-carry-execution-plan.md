# نقشهٔ اجرای زندهٔ leg کری بازیس

leg کری بک‌تست دارد (`src/carry/`) ولی اجرای زنده ندارد. پلتفرم فعلی spot تک-ابزاره است.
این سند کار باقی‌مانده را scope می‌کند. leg هستهٔ long از قبل live-ready است.

## وضعیت — گزینهٔ A تا مرحلهٔ paper ساخته شد ✓ (۲۰۲۶-۰۸-۲۹)

ماژول `src/carry/` حالا زنجیرهٔ کامل runner را دارد، تست‌شده و با بک‌تست closed-form
تطبیق داده شده:

| قطعه | فایل | وضعیت |
|---|---|---|
| اسنپ‌شات پرپ (تاریخی + زنده) | `perp_provider.py` — `HistoricalPerpProvider`, `LivePerpProvider` | ✓ |
| مدیر پوزیشن دلتا-خنثی (منطق محض) | `position_manager.py` — `CarryPositionManager` | ✓ ۱۱ تست |
| اجرا (کاغذی) + runner | `carry_runner.py` — `PaperCarryExecutor`, `CarryRunner` | ✓ ۴ تست |
| paper run + اعتبارسنجی | `scripts/run_carry_paper.py` | ✓ منطبق با `simulate_basis_carry` (اختلاف ~۴–۵pp) |

`position_manager` تصمیم/برنامه/state را مدیریت می‌کند: گیت هلد از trailing funding،
هج دلتا با band ۲٪، re-strike نوشنال با band ۱۵٪، accrual funding، و حسابداری cash صحیح
(realized P&L پرپ روی کاهش short وارد cash می‌شود). paper runner همان بازدهٔ بک‌تست را
تولید می‌کند (BTC ۴۹.۵٪ در برابر ۴۴.۳٪، maxDD ۰.۳٪) — یعنی زنجیره وفادار است.

## باقی‌مانده برای live

### ۱. `LiveCarryExecutor` (`src/carry/carry_runner.py` یا فایل جدید)
- همان اینترفیس `CarryExecutor.execute(plan) -> ExecReport` ولی سفارش واقعی ccxt:
  خرید/فروش spot + باز/بستن short پرپ هم‌اندازه (taker یا limit)
- safety gate: اگر یک leg پر شد و دیگری نه → فوراً هج یا ببند
- منتظر fill بمان، `ExecReport` را از fillهای واقعی بساز

### ۲. حلقهٔ زندهٔ scheduler (`scripts/run_carry_live.py`)
- APScheduler هر ~۸ ساعت (پیش از settlement funding): `LivePerpProvider.snapshot()` → `runner.step(snap)`
- persist کردن `runner.state` بین اجراها (JSON یا DB)
- کتاب ترکیبی: تخصیص ۷۰/۳۰ در سطح حساب بین این runner و استراتژی هسته؛ overlay هدف-نوسان روی مجموع

### ۳. reconciliation + مانیتورینگ
- هر چرخه: پوزیشن واقعی صرافی را با `runner.state` تطبیق بده؛ روی واگرایی halt
- متریک‌های Prometheus: `carry_net_delta`, `carry_accrued_funding`, `carry_leverage`, `basis_bps`
- هشدار Telegram: اجرای ناقص، basis > آستانه، نزدیک liquidation

### نیازمندی کاربر
انتخاب صرافی(ها)، API key، testnet/live، حداقل سرمایه. تخمین: ~۱ هفته برای live executor + scheduler + reconciliation.

## ریسک‌هایی که بک‌تست نمی‌گیرد (در live باید مدیریت شوند)
- **ریسک basis:** spread قیمت spot-perp در ورود/خروج و در استرس باز می‌شود
- **ریسک صرافی:** ورشکستگی/freeze برداشت (FTX نوامبر ۲۰۲۲) — کری روی چند صرافی توزیع شود
- **ADL / liquidation:** روی leg شورت پرپ در حرکت شارپ صعودی — اهرم پرپ محافظه‌کار (~۲–۳x)
- **فشردگی funding:** بازده از ۲۰۲۱ کم شده؛ overlay هدف-نوسان تا حدی جبران می‌کند

## تخمین کار
- گزینهٔ A (runner مستقل): ~۱–۲ هفته برای نسخهٔ اول paper، + ~۱ هفته سخت‌کاری live
- نیازمندی کاربر: انتخاب صرافی(ها)، API key، تصمیم testnet/live، حداقل سرمایه
