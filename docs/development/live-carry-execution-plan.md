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

## live/testnet — ساخته شد ✓ (۲۰۲۶-۰۸-۲۹)

| قطعه | فایل | وضعیت |
|---|---|---|
| `CarryExchange` (spot + futures ccxt، sandbox) | `live_executor.py` | ✓ |
| `LiveCarryExecutor` — سفارش واقعی market + unwind روی اجرای ناقص | `live_executor.py` | ✓ ۵ تست (fake exchange) |
| runner + persist + reconcile | `scripts/run_carry_live.py` | ✓ `--once` / `--loop` / `--dry-run` / `--reconcile` |
| تنظیمات credential | `settings.py` (`carry_*`) + `.env.example` | ✓ |

`LiveCarryExecutor` همان اینترفیس `CarryExecutor` را دارد — پس `CarryRunner` بدون تغییر
درایو می‌شود. جفت به‌ترتیب گذاشته می‌شود؛ اگر leg دوم بعد از پر شدن leg اول خطا دهد،
leg اول فوراً unwind و `PartialCarryFill` raise می‌شود (کتاب هیچ‌وقت directional نمی‌ماند).
`scripts/run_carry_live.py --loop` با APScheduler در ۰۰:۵۰ / ۰۸:۵۰ / ۱۶:۵۰ UTC اجرا می‌شود
(~۱۰ دقیقه پیش از settlement funding)؛ state در `data/carry_live_state.json` persist می‌شود.

### برای اجرا لازم است (کاربر)
1. اکانت testnet: [testnet.binance.vision](https://testnet.binance.vision) (spot) و
   [testnet.binancefuture.com](https://testnet.binancefuture.com) (futures) → کلیدها را در `.env` بگذار
   (`CARRY_SPOT_API_KEY`, ...). `CARRY_SANDBOX=true` پیش‌فرض.
2. `poetry run python scripts/run_carry_live.py --dry-run` — قیمت واقعی، بدون سفارش
3. `poetry run python scripts/run_carry_live.py --once` — یک چرخهٔ واقعی روی testnet
4. `poetry run python scripts/run_carry_live.py --loop` — زمان‌بندی‌شده
5. `--reconcile` — تطبیق state با پوزیشن واقعی صرافی

### باقی‌مانده (بعد از تأیید testnet)
- مانیتورینگ Prometheus/Telegram (`carry_net_delta`, `carry_leverage`, هشدار اجرای ناقص)
- کتاب ترکیبی: تخصیص ۷۰/۳۰ در سطح حساب + overlay هدف-نوسان روی مجموع (runner هسته جداست)
- سوییچ live واقعی: `CARRY_SANDBOX=false` + کلیدهای واقعی + سرمایهٔ کوچک اول

## ریسک‌هایی که بک‌تست نمی‌گیرد (در live باید مدیریت شوند)
- **ریسک basis:** spread قیمت spot-perp در ورود/خروج و در استرس باز می‌شود
- **ریسک صرافی:** ورشکستگی/freeze برداشت (FTX نوامبر ۲۰۲۲) — کری روی چند صرافی توزیع شود
- **ADL / liquidation:** روی leg شورت پرپ در حرکت شارپ صعودی — اهرم پرپ محافظه‌کار (~۲–۳x)
- **فشردگی funding:** بازده از ۲۰۲۱ کم شده؛ overlay هدف-نوسان تا حدی جبران می‌کند

## تخمین کار
- گزینهٔ A (runner مستقل): ~۱–۲ هفته برای نسخهٔ اول paper، + ~۱ هفته سخت‌کاری live
- نیازمندی کاربر: انتخاب صرافی(ها)، API key، تصمیم testnet/live، حداقل سرمایه
