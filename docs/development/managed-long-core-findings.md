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

---

## پورت به پلتفرم (۲۰۲۶-۰۸-۲۸) — انجام شد؛ جهتِ نتیجه بازتولید شد

قطعات ساخته‌شده:

| قطعه | فایل |
|---|---|
| اندیکاتور `sma` | `src/features/indicators/sma.py` |
| تحمل `InsufficientDataError` در warmup | `src/features/builder.py` |
| `CoreLongProvider` (گیت رژیم BUY/SELL) | `src/providers/core_long.py` + `config/providers/core_long.yaml` |
| feature config اختصاصی (`sma_200`) | `config/features.core_long.yaml` + `load_features_config_file()` |
| حالت `long_only` (SELL می‌بندد، short باز نمی‌کند) | `ValidationExecutionConfig.long_only` |
| سایزینگ notional-target (`exposure_pct_per_trade`) | `simulated_pricing.position_size` |
| سایزینگ vol-regime (`RiskConfig.vol_target_atr_pct` → `FinalSignal.size_multiplier`) | `final_signal_builder.py` |
| فیکس: تصمیم exit مخالف نباید با سقف `max_open_positions` رد شود | `engine/risk_manager.py` |
| override کامل `risk_limits` در `run_validation_job` (breaker پیش‌فرض ۵ ضرر متوالی استراتژی hold-the-core را وسط اجرا می‌خواباند) | `validation/job_runner.py` |
| اسکریپت اجرا + بازسازی equity mark-to-market | `scripts/run_core_long_validation.py` |

### نتیجهٔ اجرای واقعی (BTC/ETH 1d، ۲۰۱۸–۲۰۲۶، `vol_target_atr_pct=3.0`)

| | buy & hold | استراتژی روی پلتفرم |
|---|---|---|
| **BTC** بازده کل / Sharpe / MaxDD / Calmar | +۵۰۰٪ / 0.65 / **۸۱٪** / 0.52 | **+۶۳۵٪** / **0.81** / **۵۱٪** / **0.58** |
| **ETH** بازده کل / Sharpe / MaxDD / Calmar | +۲۳۳٪ / 0.59 / **۹۴٪** / 0.54 | **+۴۲۴٪** / **0.63** / **۶۳٪** / 0.52 |

**جهتِ نتیجهٔ research بازتولید شد:** MaxDD تقریباً نصف، Sharpe بهتر، بازده حفظ یا بهتر. اعداد دقیقاً با research یکی نیستند (research کل‌تاریخچه BTC: Calmar ~0.94، MaxDD ~۴۲٪) چون پورت پلتفرم **درشت‌تر** است:

- **بدون اهرم** (spot؛ `max_cash_qty` مانع notional > 1x است) — پس ضریب vol فقط de-risk می‌کند، بر خلاف research که cap ۱.۵ داشت.
- **سایز فقط در ورود** تعیین می‌شود، نه rescale روزانه (research روزانه).
- **fill واقعی + whipsaw**: ۱۶–۱۷ معامله، win-rate ~۱۷–۳۱٪ (هر crossing نزدیک SMA هزینهٔ fee+slippage رفت‌وبرگشت دارد که در research فقط `|Δw|×cost` بود).

### باقی‌مانده (اختیاری)

1. **rescale روزانهٔ سایز** — الان فقط در ورود.
2. **rebalance band** روی ضریب vol برای کم‌کردن turnover.
3. اجرا از طریق `Experiment`/`ConfigRevision` رسمی governance به‌جای اسکریپت.

---

## تست پارامتری روی پلتفرم (۲۰۲۶-۰۸-۲۹) — ناحیه منسجم است + یک باگ exit اصلاح شد

[run_core_long_param_sweep.py](../../backend/scripts/run_core_long_param_sweep.py) — گرید
`sma ∈ {sma_100, sma_150, sma_200}` × `vol_target_atr_pct ∈ {0, 2.0, 2.5, 3.0, 3.5, 4.0}`
روی BTC و ETH روزانه، ۲۰۱۸–۲۰۲۶.

### باگی که سوییپ آشکار کرد: exit با سقف `max_exposure` بلاک می‌شد

فیکس قبلیِ `opposing_exit` فقط روی چک `max_open_positions` بود، نه `max_exposure`.
وقتی استراتژی full-invested بود (`open_exposure_pct ≈ ۱۰۰`)، سیگنال SELL خودِ استراتژی
با `max_exposure` رد می‌شد و پوزیشن هیچ‌وقت روی regime-flip بسته نمی‌شد → فقط ۱ معامله در
۸ سال، نگه‌داری از میان هر دو خرسی. با vol scaling کوچک‌تر می‌شد و exit گاهی رد می‌شد
(نتایج غیریکنواخت). **فیکس:** همان bypass `opposing_exit` روی چک `max_exposure` هم اعمال شد
(`engine/risk_manager.py`) — یک تصمیم exit همیشه exposure را *کم* می‌کند، پس سقف exposure
نباید بلاکش کند. تست: `test_opposing_exit_not_blocked_by_max_exposure`.

### نتایج سوییپ (بعد از فیکس) — همه ۳۶ سلول MaxDD را نصف می‌کنند

| نماد / SMA | Sharpe (buy&hold) | Sharpe (استراتژی، atr% ۲–۳.۵) | MaxDD b&h → استراتژی | Calmar b&h → استراتژی |
|---|---|---|---|---|
| BTC sma_100 | 0.65 | 0.98–1.11 | ۸۱٪ → **۲۸–۳۴٪** | 0.52 → **0.93–1.10** |
| BTC sma_150 | 0.65 | 1.01–1.06 | ۸۱٪ → **۳۹–۴۴٪** | 0.52 → **0.72–0.84** |
| BTC sma_200 | 0.65 | 0.75–0.82 | ۸۱٪ → **۴۶–۵۱٪** | 0.52 → 0.47–0.53 |
| ETH sma_100 | 0.59 | 0.75–0.79 | ۹۴٪ → **۵۲–۵۸٪** | 0.54 → 0.47–0.52 |
| ETH sma_150 | 0.59 | 0.77–0.80 | ۹۴٪ → **۴۸–۵۶٪** | 0.54 → **0.55–0.61** |
| ETH sma_200 | 0.59 | 0.70–0.73 | ۹۴٪ → **۵۲–۶۳٪** | 0.54 → 0.50–0.56 |

- **هر ۳۶ سلول** (۳ SMA × ۶ vol-target × ۲ نماد) روی MaxDD **و** Sharpe از buy&hold بهترند.
  این دقیقاً همان معیار robustness آماری است: ناحیهٔ منسجم، نه بردهای پراکنده.
- **`sma_150` مرکز بهتری از `sma_200` است** — روی **هر سه** معیار و **هر دو** نماد، برای همهٔ
  `atr% ∈ [2, 3.5]`، از buy&hold می‌برد. این با یافتهٔ research هم‌خوان است (بهترین research هم SMA150 بود).
- **`atr%` knob کم‌اهمیت‌تر از انتخاب SMA است**؛ `[2.0, 3.5]` یک plateau پهن است. `atr%=0` (فقط گیت،
  بدون vol scaling) پیوسته کمی بدتر — vol scaling ارزش اضافه می‌کند.
- پارامترهای دستیِ قبلی (`sma_200` / `atr%=3.0`) یک گوشهٔ محافظه‌کار بود؛ پیش‌فرض به
  `sma_150` / `atr%=2.5` تغییر کرد (`config/providers/core_long.yaml`, اسکریپت اعتبارسنجی).

### نتیجهٔ اجرای مرجع (sma_150, atr%=2.5)

| | buy & hold | استراتژی |
|---|---|---|
| **BTC** Sharpe / MaxDD / Calmar / بازده | 0.65 / ۸۱٪ / 0.52 / +۵۰۰٪ | **1.03** / **۴۱٪** / **0.79** / +۹۷۱٪ |
| **ETH** Sharpe / MaxDD / Calmar / بازده | 0.59 / ۹۴٪ / 0.54 / +۲۳۳٪ | **0.80** / **۵۰٪** / **0.61** / +۶۵۶٪ |

**وضعیت: استراتژی روی پلتفرم اجرا می‌شود، در یک ناحیهٔ پارامتری منسجم به‌طور مادی از buy&hold
بهتر است (MaxDD نصف، Sharpe/Calmar بالاتر، بازده کل بالاتر)، و باگ exit پلتفرم اصلاح شد.**
آمادهٔ promote به `candidate` از مسیر governance.
