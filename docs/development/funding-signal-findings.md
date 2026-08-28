# بررسی فرضیه‌ی جدید: نرخ Funding پرپچوال — رد شد

بعد از بسته‌شدن کامل TA کلاسیک (نگاه کنید به [edge-investigation-findings.md](./edge-investigation-findings.md) و [provider-edge-htf-experiment-plan.md](./provider-edge-htf-experiment-plan.md) §10)، اولین **کلاس فرضیه‌ی متفاوت** که تست شد: نرخ funding قرارداد پرپچوال.

**فرضیه‌ی اقتصادی:** funding پرداخت دوره‌ای بین long و short پرپ است و مستقیماً «ازدحام / اهرم پوزیشن‌ها» را نشان می‌دهد، نه مسیر قیمت. انتظار: funding مثبت و بالای پایدار = long های پراهرم و ازدحام‌شده = ریسک squeeze بالا (سیگنال contrarian short)؛ funding منفی پایدار = ازدحام short (contrarian long). این یک منبع اطلاعاتی جدا از trajectory قیمت است — دقیقاً همان چیزی که §10 توصیه کرد.

**نتیجه‌ی نهایی: رد شد.** سیگنال funding ~۵۰٪ با مومنتوم خام قیمت هم‌بستگی دارد (پس framing «دنبال‌کردن funding» چیزی جز trend-following از پیش‌ردشده نیست)، جهتش بین BTC و ETH برعکس است (نشانه‌ی دو overfit مستقل، نه یک ادج)، و در جدیدترین یک‌سوم داده به صفر میل می‌کند.

---

## روش

- **اسکریپت:** [run_funding_signal_research.py](../../backend/scripts/run_funding_signal_research.py) — آماری محض، مثل `run_signal_research.py`: بدون Decision Engine، بدون provider، بدون execution. صرفاً غربال «آیا این سیگنال قدرت پیش‌بینی خام دارد؟» قبل از ساختن هر provider/feature.
- **داده:** تاریخچه‌ی کامل funding از Binance (`ccxt.fetch_funding_rate_history`, پرینت هر ۸ ساعت) برای پرپ BTC/USDT و ETH/USDT، ۲۰۱۹-۰۹ تا ۲۰۲۶-۰۸ (~۷۶۰۰ پرینت، ~۲۵۴۴ بار روزانه)، کش در `data/cache/binance_funding_*_8h.csv`. OHLCV اسپات از همان مسیر `load_ohlcv` بقیه‌ی pipeline.
- **قاعده‌ی look-ahead:** بار روزانه‌ی t با تایم‌استمپ ۰۰:۰۰ UTC، در ۰۰:۰۰ روز t+1 بسته می‌شود. پرینت‌های funding در ۰۰:۰۰/۰۸:۰۰/۱۶:۰۰ هستند، پس مجموع funding روز t تا بسته‌شدن بار t شناخته‌شده است → سیگنال backward-looking. مقایسه فقط با `fwd_ret_h = close[t+h]/close[t]-1` (از `signal_evaluator.compute_forward_targets`).
- **فیچرها (همه backward-looking):** `fund_day` (مجموع درصدی روز)، `fund_trail` (مجموع غلتان ۳ روزه)، `fund_rank` (رتبه‌ی percentile مقدار جاری در پنجره‌ی غلتان ۱۸۰ روزه).
- **framing های تست‌شده:** `contrarian_rank` (rank بالا → DOWN)، `momentum_rank` (rank بالا → UP)، `sign_contrarian` (fund_trail>0 → DOWN). × آستانه‌ی percentile {80, 90, 95} × horizon {1, 3, 7, 14, 30} روز.

### درس مهم متدولوژیک: baseline اشتباه، false positive تولید می‌کند

نسخه‌ی اول اسکریپت سیگنال را با baseline **۵۰٪ (شیر یا خط)** می‌سنجید و «PASS» می‌داد: BTC contrarian h=30 با net expectancy +۲.۸۵٪، ETH momentum h=30 با +۵.۳۳٪. هر دو **گمراه‌کننده** بودند:

1. **drift بازار.** میانگین بی‌قید `fwd_ret_30` روی BTC = **+۴.۱٪** و روی ETH = **+۶.۰٪** (بازار صعودی بلندمدت ۲۰۱۹–۲۰۲۶). هر سیگنالی که خالص‌اش long باشد این drift را مفت می‌گیرد. ETH momentum h=30 با +۵.۳۳٪ در واقع **بدتر از buy-and-hold** بود.
2. **هم‌پوشانی horizon.** h=30 روی بار روزانه یعنی n=۴۰۰–۱۲۰۰ «معامله»ی به‌شدت خودهم‌بسته — عملاً ۱۵–۳۰ اپیزود مستقل، نه ۱۰۰۰ شرط مستقل. win% ۵۸٪ روی این‌ها معنای ۵۸٪ روی ۱۰۰۰ بار مستقل را ندارد.

نسخه‌ی اصلاح‌شده‌ی اسکریپت این‌ها را برطرف می‌کند:
- **null مبتنی بر drift:** یک سیگنال جهت‌دار به‌طور رایگان `E[side] × E[fwd_ret]` می‌گیرد. ادج واقعی = expectancy **مازاد بر این null**. این باید بعد از کارمزد مثبت باشد، هم روی نمونه‌ی کامل (هم‌پوشان) و هم روی زیرنمونه‌ی **غیرهم‌پوشان** (سیگنال‌ها با فاصله‌ی ≥ horizon).
- **پایداری زیر-بازه:** net expectancy خام (نه فقط مازاد بر null) باید در ≥۲ از ۳ زیر-بازه‌ی متوالی مثبت بماند.
- **سازگاری بین‌نمادی:** یک ادج ساختاری funding باید روی BTC و ETH **هم‌جهت** باشد (همان مکانیزم، ~۰.۹ هم‌بسته).

---

## نتایج (اسکریپت اصلاح‌شده)

| نماد | framing های PASS | جزئیات |
|---|---|---|
| BTC/USDT | `contrarian_rank` (۱ ردیف: p90 h=14) | net expectancy **−۰.۲۱٪** (منفی!) — فقط به‌خاطر null منفی‌تر و قاعده‌ی زیر-بازه پاس شد. نویز. |
| ETH/USDT | `momentum_rank` (۱۰ ردیف، همه h=14/30) | excess بزرگ (+۲.۴ تا +۶.۴٪)، ولی جهت **مخالف** BTC. |

**`VERDICT: REJECT — framings که پاس می‌شوند بین نمادها فرق دارند ({BTC: contrarian, ETH: momentum})؛ هیچ فرضیه‌ی واحدی بین نمادها دوام نمی‌آورد.`**

### سه دلیل رد

1. **جهت برعکس BTC vs ETH.** BTC فقط با «fade کردن funding» چیزی نشان می‌دهد، ETH فقط با «دنبال‌کردن funding». اگر ادج از ساختار funding می‌آمد باید هم‌علامت باشد. این امضای دو overfit مستقل است.
2. **هم‌بستگی ~۰.۵۰ با مومنتوم قیمت.** `corr(fund_rank, بازده ۳۰ روز گذشته)` روی هر دو نماد **۰.۵۰** است (و `corr(fund_rank, price/SMA30)` ~۰.۴۶–۰.۵۲). یعنی framing برنده‌ی ETH (`momentum_rank`، «وقتی funding بالاست long بزن») تقریباً همان سیگنال trend-following است که در [candidate-stability-findings.md](./candidate-stability-findings.md) به‌عنوان regime-unstable رد شد — فقط با ماسک funding.
3. **زوال در زیر-بازه‌ی آخر.** همه‌ی PASS های ETH در یک‌سوم آخر داده (~۲۰۲۴–۲۰۲۶) عملاً به صفر می‌رسند. مثال (`momentum_rank p90 h=30`): net زیر-بازه‌ها +۷.۶۲ / +۴.۳۰ / **+۰.۷۶**. مثال (`p95 h=14`): +۲.۹۵ / +۴.۳۳ / **+۰.۰۳**. الگوی کلاسیک artifact یک‌پنجره‌ای که رو به جلو generalize نمی‌شود.

### زیرساخت سالم است

اسکریپت از همان `load_ohlcv` / `compute_forward_targets` / `_net_of_fees` / `_trade_pnls` بقیه‌ی pipeline استفاده می‌کند. هزینه‌ی رفت‌وبرگشت از `load_default_fill_model()` واقعی (~۰.۳٪). خطای اولیه صرفاً در **baseline غربال** بود (۵۰٪ به‌جای drift-adjusted)، نه در داده یا محاسبات — و همان اصلاح، false positive را به REJECT درست تبدیل کرد.

---

## جمع‌بندی و گام بعد

| # | یافته | وضعیت |
|---|---|---|
| 1 | غربال با baseline ۵۰٪ روی BTC و ETH «PASS» می‌داد (h=30) | ⚠️ false positive — baseline اشتباه بود |
| 2 | با null مبتنی بر drift + نمونه‌ی غیرهم‌پوشان، BTC عملاً هیچ، ETH فقط `momentum_rank` | ✅ اصلاح شد |
| 3 | `momentum_rank` ~۰.۵۰ با مومنتوم قیمت هم‌بسته = trend-following از پیش‌ردشده با ماسک funding | ✅ تست و رد شد |
| 4 | جهت PASS بین BTC (contrarian) و ETH (momentum) برعکس | ✅ رد قطعی — فرضیه‌ی واحد بین‌نمادی وجود ندارد |
| 5 | PASS های ETH در یک‌سوم آخر داده به صفر می‌رسند | ✅ زوال رو به جلو |

**نرخ funding به‌تنهایی ادج جهت‌دار قابل‌اتکایی نمی‌دهد.** بخشی از اطلاعاتش صرفاً مومنتوم قیمت بازبسته‌بندی‌شده است، و بخش مستقلش (رتبه‌ی نسبی funding) بین نمادها ناسازگار و رو به جلو ناپایدار است.

**گام بعدی منطقی** — کلاس‌های فرضیه‌ی دیگر که هنوز تست نشده‌اند و اطلاعاتشان کمتر با قیمت هم‌بسته است:
- **basis / term structure** (پرپ منهای اسپات، یا کوارترلی منهای اسپات) — انتظار قیمت‌گذاری‌شده‌ی بازار، نه realized؛ ولی احتمالاً مثل funding با مومنتوم هم‌بسته.
- **open interest + جهت قیمت** (افزایش OI با قیمت صعودی = پوزیشن تازه‌ی long؛ کاهش OI = بستن پوزیشن) — نیازمند داده‌ی OI که Binance فقط ~۳۰ روز اخیر را از طریق `/futures/data` می‌دهد؛ برای تاریخچه‌ی بلند باید منبع دیگر.
- **long/short account ratio** — مثل بالا، محدودیت تاریخچه.
- **volatility regime targeting** (نه پیش‌بینی جهت — صرفاً کاهش/افزایش exposure بر اساس رژیم نوسان؛ Phase 2 قبلاً ادج magnitude/volatility-clustering واقعی پیدا کرده بود).

آخرین مورد (volatility targeting) امیدوارکننده‌ترین است چون تنها یافته‌ی مثبت کل تحقیق (Phase 2 در [candidate-stability-findings.md](./candidate-stability-findings.md)) دقیقاً همین بود — و بر خلاف جهت، اثر خرج‌کردنی دارد.
