# مسیر گزینه ۱: هستهٔ long ریسک-منضبط — **PASS** (تبدیل ریسک، نه alpha)

پس از رد شدن هر هفت کلاس فرضیهٔ جهت‌دار/ادج‌محور (نگاه کنید به [edge-investigation](./edge-investigation-findings.md)، [candidate-stability](./candidate-stability-findings.md)، [provider-edge-htf §10](./provider-edge-htf-experiment-plan.md)، [funding-signal](./funding-signal-findings.md)، [volatility-targeting](./volatility-targeting-findings.md)، [cross-sectional-momentum](./cross-sectional-momentum-findings.md))، این بررسی سؤال متفاوت و صادقانه‌تری می‌پرسد:

**با فرض اینکه نگه‌داشتن بتای کریپتو drift مثبت بلندمدت دارد ولی drawdown ~۸۰–۹۵٪، آیا افزودن (الف) یک سوییچ risk-off مبتنی بر trend و (ب) سایزینگ vol-targeted، یک وسیلهٔ نقلیهٔ ریسک-تعدیل‌شدهٔ به‌طور مادی بهتر می‌سازد — Calmar بالاتر، drawdown خیلی کمتر — با حفظ بخش عمدهٔ بازده؟**

**نتیجه: بله. PASS — و robust.** این alpha نیست (یک ناکارآمدی بازار ادعا نمی‌شود)؛ این harvest کردن پریمیوم شناخته‌شدهٔ trend + vol-targeting است که پشتوانهٔ آکادمیک و صنعتی قوی دارد (Moskowitz-Ooi-Pedersen؛ AQR/Man AHL). ولی یک استراتژی مشروع و قابل‌پیاده‌سازی است که پلتفرم فعلی می‌تواند اجرا کند.

---

## روش

[run_managed_long_core_research.py](../../backend/scripts/run_managed_long_core_research.py) — آماری محض. BTC/USDT و ETH/USDT روزانه، ۲۰۱۷-۰۸ تا ۲۰۲۶-۰۸.

- **گیت رژیم:** in-market وقتی `close > SMA(N)`، با گزینهٔ نیاز به تداوم `confirm` روز. trend به‌عنوان سوییچ risk-off، **نه** پیش‌بینی جهت.
- **vol targeting:** `w = target_ann_vol / realized_vol(W)`، کلیپ `[0, cap]`.
- **ترکیب:** `w[t] = in_market[t] × clip(target/vol[t], 0, cap)`، اعمال روی `r[t+1]`.
- **گرید:** `SMA_N ∈ {100,150,200}` × `confirm ∈ {0,3}` × `vol_W ∈ {20,30}` × `target ∈ {0.5,0.6,0.8}` × `cap ∈ {1.0,1.5}` = ۷۲ ترکیب/نماد.
- **معیار:** Calmar (ann_return/max_dd) و Max Drawdown — هر دو scale-invariant، پس با تغییر exposure دستکاری نمی‌شوند.
- **PASS:** Calmar باید buy&hold را ≥۱.۳× ببرد **و** maxDD ≤ ۰.۷۵× buy&hold، روی کل نمونه + ≥۲/۳ زیر-بازه، روی **هر دو** نماد.
- هزینهٔ turnover روزانه از `load_default_fill_model` روی `|Δw|` کسر می‌شود؛ بازدهٔ out-of-market صفر فرض شده (محافظه‌کارانه — نرخ بدون‌ریسک واقعی به‌نفع نسخهٔ managed بود).

---

## نتایج

### کل تاریخچه (۲۰۱۷-۰۸ → ۲۰۲۶-۰۸)

| | buy & hold | بهترین managed (SMA150, W30, tgt0.5–0.6, cap1.5) |
|---|---|---|
| **BTC** Calmar / maxDD / Sharpe / بازده سالانه | 0.66 / 83% / 0.82 / 55% | ~0.93 / **~42%** / ~1.01 / ~39% |
| **ETH** Calmar / maxDD / Sharpe / بازده سالانه | 0.65 / 94% / 0.71 / 61% | ~0.95 / **~46%** / ~0.96 / ~44% |

۳ ترکیب مشترک روی هر دو نماد (`SMA150, c0, W∈{20,30}, tgt∈{0.5,0.6}, cap1.5`). زیر-بازه‌ها: **زیر-بازهٔ ۱ (۲۰۱۷–۲۰۲۰) گیت Calmar را رد می‌کند** (بازار گاوی هیولاوار؛ نشستن بیرون به Calmar ضربه می‌زند) ولی حفاظت drawdown را حفظ می‌کند (maxDD ~۰.۴۲ در برابر ~۰.۸۳). زیر-بازه‌های ۲ و ۳ (۲۰۲۰+) قوی PASS (S calmar ۱.۱–۱.۶۵ در برابر B ۰.۵–۱.۱).

### چک robustness — همان screen از ۲۰۲۲-۰۱ (شامل خرسیِ ۲۰۲۲): تقویت شد، نه فروپاشی

| | buy&hold Calmar | managed Calmar | ترکیب‌های PASS |
|---|---|---|---|
| BTC ۲۰۲۲+ | 0.43 | ~1.2 | ۳۶/۷۲ |
| ETH ۲۰۲۲+ | 0.20–0.31 | ~0.9 | ۴۱/۷۲ |
| **مشترک هر دو نماد** | | | **۲۱/۷۲** (در برابر ۳/۷۲ کل‌تاریخچه) |

**این تفاوت تعیین‌کننده با cross-sectional momentum است:** آن‌جا محدود کردن به ۲۰۲۲+ نتیجه را **نابود** کرد (۱۷→۳، ناحیه جابه‌جا شد). این‌جا ۲۰۲۲+ نتیجه را **تقویت** کرد (۳→۲۱ مشترک، ناحیهٔ پارامتر منسجم می‌ماند: SMA۱۵۰–۲۰۰، W۲۰–۳۰، tgt۰.۵–۰.۸). دلیل: ۲۰۲۲+ شامل خرسیِ ۲۰۲۲ است — دقیقاً جایی که یک overlay ریسک-off ارزش خودش را نشان می‌دهد. ضعف نسبی کل‌تاریخچه فقط به‌خاطر بازارهای گاوی ۲۰۱۷–۲۰۲۰ بود.

---

## قضاوت و هشدارها

**PASS با اطمینان متوسط-بالا.** دلایل اعتماد:
- روی **هر دو** نماد با **همان** پارامترها کار می‌کند (برخلاف funding که علامتش برعکس بود).
- ناحیهٔ پارامتر **منسجم و پیوسته** است، نه نقاط پراکنده (برخلاف ADX و cross-sectional).
- out-of-sample (۲۰۲۲+) **تقویت** می‌شود، نه فروپاشی (برخلاف cross-sectional).
- baseline و معیار درست‌اند (Calmar/maxDD، scale-invariant — برخلاف false-positive اولیهٔ funding/vol-targeting).
- **priorِ قوی:** این یک اثر مستندشده و منتشرشده است، نه ادعای یک ناکارآمدی جدید.

هشدارها:
- **alpha نیست.** بازده سالانه از buy&hold **کمتر** است (~۴۰٪ در برابر ~۵۵٪). ارزش در نصف‌شدن drawdown و بالارفتن Calmar/Sharpe است.
- **SMA۲۰۰ چیزی است که همه تماشا می‌کنند** — ریسک reflexivity/crowding. کاهش: SMA۱۵۰ هم کار می‌کند (عدد جادویی واحد نیست)، و این یک فیلتر **ریسک** است نه پیش‌بینی‌کنندهٔ بازده.
- **turnover:** vol targeting روزانه rebalance می‌کند؛ Σ|Δw| ~۱۱۰ روی ۸ سال ≈ ۱۴/سال، ~۲٪/سال drag (در بازده‌های net لحاظ شده). پیاده‌سازی واقعی به یک rebalance band نیاز دارد.
- **whipsaw:** `confirm=0` برنده شد؛ SMA آهسته (۱۵۰–۲۰۰ روزه) به‌اندازهٔ کافی صاف هست که guard نخواهد.

### پارامتر پیشنهادی برای پورت

میانهٔ ناحیه، نه لبه: **SMA۲۰۰ گیت رژیم، realized-vol پنجرهٔ ۳۰ روزه، target نوسان سالانهٔ ۰.۵–۰.۶، cap ۱.۰–۱.۵.** نسخهٔ محافظه‌کار: `tgt=0.5, cap=1.0` (بدون اهرم). نسخهٔ کمی تهاجمی‌تر: `tgt=0.6, cap=1.5`.

---

## گام بعد: پورت به پلتفرم

معماری Engine-Centric این را مستقیم پشتیبانی می‌کند:

1. **`CoreLongProvider`** — یک `SignalProvider` که وقتی `close > SMA(N)` سیگنال LONG با confidence بالا می‌دهد، وگرنه HOLD. SMA از `FeatureBuilder` می‌آید (نه محاسبهٔ داخل provider).
2. **سیاست سایزینگ vol-targeted** در لایهٔ RiskManager/execution — `position_size *= clip(target_vol / realized_vol, 0, cap)`. این باید یک knob پیکربندی‌پذیر باشد، نه hard-code.
3. **config YAML** برای provider و پارامترهای سایزینگ.
4. **اعتبارسنجی از طریق `ValidationHarness`** روی BTC+ETH — تأیید که پلتفرم نتیجهٔ research را بازتولید می‌کند (Calmar/maxDD/Sharpe در همان محدوده).
5. تست‌های unit برای provider و سیاست سایزینگ.

این تنها کلاس فرضیه‌ای است که از کل تحقیق جان به‌در برد. اگر پورت، نتیجهٔ research را در پلتفرم واقعی بازتولید کند، **این استراتژی قابل‌عرضهٔ پروژه است.**
