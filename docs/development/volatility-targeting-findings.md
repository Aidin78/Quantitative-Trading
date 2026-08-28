# بررسی فرضیه: Volatility-Regime Position Sizing — رد شد (فقط حرکت روی frontier)

بعد از رد funding ([funding-signal-findings.md](./funding-signal-findings.md))، دومین کلاس فرضیه‌ی غیر-جهتی: **سایزینگ بر اساس رژیم نوسان** (نه پیش‌بینی جهت).

**پایه:** تنها یافته‌ی آماری مثبت کل pipeline، Phase 2 است — نوسان/magnitude خودهم‌بسته است (volatility clustering) روی BTC. جهت غیرقابل‌پیش‌بینی است، ولی بزرگی نوسان تا حدی هست. نمی‌توان از بزرگی نوسان یک «سمت» ساخت، ولی می‌توان روی آن **سایز** گرفت: exposure long را معکوسِ نوسانِ پیش‌بینی‌شده مقیاس کن. نتیجه‌ی کلاسیک (سهام): این کار Sharpe را بالا و drawdown را پایین می‌برد چون spike های نوسان حول drawdown ها خوشه می‌شوند (leverage effect).

**نتیجه‌ی نهایی: رد شد.** روی کریپتو، این overlay هیچ ادج Sharpe نمی‌سازد — فقط بازده را ۱:۱ با drawdown معاوضه می‌کند (حرکت روی همان efficient frontier)، یا با cap>1 صرفاً اهرم اضافه می‌کند. هیچ‌کدام alpha نیست.

---

## روش

[run_volatility_targeting_research.py](../../backend/scripts/run_volatility_targeting_research.py) — آماری محض. BTC/USDT و ETH/USDT روزانه، ۲۰۱۷-۰۸ تا ۲۰۲۶-۰۸ (۳۲۹۸ بار).

- **وزن استراتژی:** `w[t] = target_vol / predicted_vol[t]`، کلیپ به `[0, cap]`. `predicted_vol[t]` = انحراف‌معیار بازده‌های `[t-W+1 .. t]` (شناخته‌شده در بسته‌شدن t)، اعمال روی بازده روز `t+1`.
- **گرید:** `W ∈ {10, 20, 30, 60}` روز × `target_ann_vol ∈ {0.4, 0.6, 0.8}` × `cap ∈ {1.0, 2.0}` (۲۴ ترکیب هر نماد).
- **هزینه:** turnover روزانه × یک‌طرفه `(fee+slippage)/10000` از `load_default_fill_model()`.
- **معیار:** **Sharpe و Max Drawdown** (هر دو scale-invariant — با تغییر exposure متوسط، دستکاری نمی‌شوند). درس گرفته‌شده از false-positive غربال funding: baseline درست + معیار درست.
- **PASS:** Sharpe استراتژی باید buy&hold را ≥۰.۱۵ ببرد، هم روی کل نمونه و هم در ≥۲ از ۳ زیر-بازه، و روی **هر دو** نماد.

---

## نتایج

| | buy & hold | بهترین vol-target (cap=1, de-risk) | بهترین (cap=2) |
|---|---|---|---|
| **BTC** Sharpe / maxDD | 0.82 / 83% | ~0.78 / **61%** (W60,tgt0.4) | ~0.82 / 90% (اهرم) |
| **ETH** Sharpe / maxDD | 0.71 / 94% | ~0.73 / **64%** (W60,tgt0.4) | ~0.74 / 89% |

**`VERDICT: REJECT` — هیچ ترکیبی Sharpe را ≥۰.۱۵ روی کل نمونه + ≥۲/۳ زیر-بازه روی هر دو نماد نبرد. PASS configs: ۰/۲۴ روی هر نماد.**

### چرا رد

1. **زیر-بازه‌ها Sharpe را نمی‌برند.** تقریباً در هر ترکیب و هر دو نماد، Sharpe استراتژی در ۲ از ۳ زیر-بازه **پایین‌تر یا برابر** buy&hold است. مثال BTC (W30,tgt0.8,cap2): زیر-بازه‌ها `0.71 vs 0.83` / `0.70 vs 0.80` / `1.07 vs 1.04` — دو باخت، یک برد ناچیز.
2. **de-risking (cap=1) فقط حرکت روی frontier است.** ترکیب‌های target پایین drawdown را واقعاً کم می‌کنند (BTC ۸۳٪→۶۱٪)، ولی Sharpe هم از ۰.۸۲ به ~۰.۷۸ افت می‌کند و بازده سالانه هم پایین می‌آید. کمتر ریسک، کمتر بازده، ~همان نسبت — یعنی هیچ ناهار مجانی.
3. **بهترین Calmar ها فقط اهرم‌اند.** همه‌ی ردیف‌های بالای Calmar، `cap=2` با وزن متوسط >۱ هستند — بازده بیشتر از اهرم‌گیری، نه timing؛ و maxDD شان اغلب **بدتر** از buy&hold است.

### چرا کلاسیک سهام این‌جا کار نمی‌کند

نتیجه‌ی «vol targeting → Sharpe بهتر» در شاخص‌های سهام به هم‌بستگی منفی قوی نوسان-بازده (leverage effect) وابسته است. در کریپتو این اثر ضعیف‌تر و نویزی‌تر است، و بزرگ‌ترین حرکت‌های صعودی کریپتو **هم** پرنوسان‌اند — پس کم‌کردن سایز در نوسان بالا، upside را هم از دست می‌دهد.

---

## جمع‌بندی وضعیت کلان تحقیق

پس از این مرحله، همه‌ی کلاس‌های فرضیه‌ی امتحان‌شده رد شده‌اند:

| کلاس فرضیه | نتیجه | سند |
|---|---|---|
| TA کلاسیک (EMA/MACD/RSI/ADX/BB/ST/MS) روی 1h/4h/1d | رد | edge-investigation, provider-edge-htf §10 |
| ensemble / majority-vote سیگنال‌های trend | رد | candidate-stability |
| گیت magnitude/volatility روی سیگنال جهت‌دار (Phase 3) | رد | candidate-stability |
| تایم‌فریم بزرگ‌تر (4h/1d) | رد | candidate-stability, provider-edge-htf |
| order-flow / CMF | رد | candidate-stability |
| ADX trend-strength روی 1d (sweep پارامتر) | رد (artifact ۱۸ماهه) | provider-edge-htf §10 |
| نرخ funding پرپچوال (contrarian/momentum) | رد | funding-signal |
| **volatility-regime sizing** | **رد (فقط frontier move)** | این سند |

**یافته‌ی انباشته:** BTC/USDT و ETH/USDT روی بارهای روزانه/درون‌روزی، ۲۰۱۷–۲۰۲۶، با هزینه‌ی واقعی، ادج جهت‌دار یا risk-timing قابل‌تعمیم ندارند. تنها واقعیت آماری robust (خوشه‌بندی نوسان) به بهبود Sharpe تبدیل نمی‌شود.

### گزینه‌های پیش رو (تصمیم استراتژیک)

1. **پذیرش «long کریپتو با guardrail» به‌عنوان محصول.** vol-scaled sizing برای سقف‌زدن drawdown + یک kill-switch رژیمی ساده. alpha نیست، ولی محصول مشروعی است؛ ارزش پلتفرم آن‌وقت انضباط اجرا + مدیریت ریسک است، نه تولید سیگنال.
2. **تغییر universe به cross-sectional.** رتبه‌بندی سبدی از N ارز بر اساس بازده/مومنتوم گذشته، long سرِ صف / short تهِ صف، rebalance هفتگی. مکانیزم کاملاً متفاوت از همه‌ی چیزهای امتحان‌شده (که همگی timing تک‌دارایی بودند). **cross-sectional momentum کریپتو یکی از معدود ادج‌های کریپتو با پشتوانه‌ی آکادمیک است.** داده‌اش رایگان است (همان OHLCV، فقط چند ده ارز).
3. **alt-data واقعاً orthogonal.** on-chain flows، exchange net-flows، عرضه‌ی stablecoin، skew ضمنی آپشن. اکثراً تاریخچه‌ی بلند رایگان ندارند.
4. **پذیرش null.** مستندسازی «ادجی یافت نشد» و توقف.

پیشنهاد: **گزینه ۲** — تنها مسیر با مکانیزم جدید، داده‌ی رایگان با تاریخچه‌ی کافی، و پشتوانه‌ی بیرونی.
