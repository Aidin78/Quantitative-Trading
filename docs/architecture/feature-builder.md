# لایه Feature Builder

## چرا این لایه لازم است؟

در معماری Engine-Centric سه نقش **متفاوت** داریم که نباید قاطی شوند:

| نقش | سؤال | مثال |
|-----|------|------|
| **Feature Builder** | بازار **چه شکلی** است؟ | RSI=28, EMA cross=true, ATR=450 |
| **Signal Provider** | با این ویژگی‌ها **چه نظری** داریم؟ | BUY, confidence=0.75 |
| **Decision Engine** | آیا این نظر **قابل اجرا** است؟ | approved / rejected |

بدون Feature Builder، هر Provider مجبور است:
- اندیکاتورها را خودش محاسبه کند → **تکرار کد**
- در Validation و Live محاسبات متفاوت داشته باشد → **ناهمسانی**
- منطق تحلیل را با منطق محاسبه قاطی کند → **Provider سنگین و غیرقابل تست**

```
❌ بدون Feature Builder:

Provider A: calculate RSI → interpret → signal
Provider B: calculate RSI → interpret → signal   ← RSI دوبار محاسبه شد
Engine:     calculate ATR for filter               ← ATR جداگانه

✅ با Feature Builder:

OHLCV → FeatureBuilder → FeatureSet + MarketContext
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          Provider A      Provider B      Engine (filter)
          (interpret)     (interpret)     (uses context)
```

## جایگاه در معماری

```
┌─────────────────────────────────────────────────────────┐
│                   Decision Engine                        │  ← تصمیم
├─────────────────────────────────────────────────────────┤
│                   Signal Providers                       │  ← نظر
├─────────────────────────────────────────────────────────┤
│              ★ Feature Builder Layer ★                   │  ← ویژگی
├─────────────────────────────────────────────────────────┤
│              MarketDataProvider (OHLCV)                  │  ← داده خام
└─────────────────────────────────────────────────────────┘
```

**Feature Builder زیرساخت مشترک است — نه plug-in و نه جزء Engine.**

## مسئولیت‌ها

### Feature Builder می‌کند

| کار | توضیح |
|-----|--------|
| محاسبه اندیکاتورها | RSI, EMA, MACD, Bollinger, ATR, ... |
| ساخت `FeatureSet` | مجموعه featureهای محاسبه‌شده برای یک نقطه زمانی |
| ساخت `MarketContext` | trend, volatility, session — برای Engine filter |
| Cache | جلوگیری از محاسبه مجدد در همان چرخه |
| Versioning | `feature_set_version` برای reproducibility |

### Feature Builder نمی‌کند

| کار | چرا نه | کجا |
|-----|--------|-----|
| تصمیم BUY/SELL | نظر = Provider | `providers/` |
| قوانین ریسک | تصمیم = Engine | `engine/` |
| خواندن CSV/API | داده خام = Data adapter | `data/` |
| ذخیره در DB | خروجی = Sink | `sinks/` |

## قراردادها

### FeatureSet

```python
@dataclass(frozen=True)
class FeatureSet:
  symbol: str
  timeframe: str
  timestamp: datetime
  version: str                    # e.g. "v1"

  # قیمت
  close: float
  open: float
  high: float
  low: float
  volume: float

  # اندیکاتورها — flat namespace یا nested
  indicators: dict[str, float]    # {"rsi_14": 28.5, "ema_12": 67100, ...}
  flags: dict[str, bool]          # {"ema_cross_bullish": True, ...}
  levels: dict[str, float]        # {"support": 66000, "resistance": 68500}
```

### FeatureBuilder protocol

```python
class FeatureBuilder(Protocol):
  def build(
    self,
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
  ) -> tuple[FeatureSet, MarketContext]:
    """OHLCV → features + context. تنها نقطه محاسبه اندیکاتور."""
    ...
```

### Provider ورودی جدید

Provider دیگر `df` خام نمی‌گیرد — `FeatureSet` می‌گیرد:

```python
class SignalProvider(Protocol):
  def analyze(
    self,
    features: FeatureSet,
    context: MarketContext,
  ) -> StrategySignal: ...
```

**مزیت:** Provider فقط **تفسیر** می‌کند — سبک، تست‌پذیر، بدون وابستگی به pandas-ta.

## Feature Registry

اندیکاتورها declarative تعریف می‌شوند:

```yaml
# config/features.yaml
version: v1
indicators:
  - name: rsi_14
    type: rsi
    params: { period: 14 }
  - name: ema_12
    type: ema
    params: { period: 12 }
  - name: ema_26
    type: ema
    params: { period: 26 }
flags:
  - name: ema_cross_bullish
    expr: "ema_12 > ema_26"
context:
  trend: { method: ema_slope, fast: 12, slow: 26 }
  volatility: { method: atr_pct, period: 14 }
```

```
config/features.yaml
        │
        ▼
FeatureRegistry (parse config)
        │
        ▼
FeatureBuilder.build(df) → FeatureSet
```

افزودن RSI(21) = یک خط در YAML — نه تغییر در Provider.

## جریان در Runtime

```
PlatformRuntime.run_cycle()
    │
    ├─ 1. data_provider.get_latest()        → OHLCV
    ├─ 2. feature_builder.build(df)         → FeatureSet + MarketContext
    ├─ 3. providers.analyze(features, ctx)  → list[StrategySignal]
    ├─ 4. engine.process(signals, ctx)      → Decision
    └─ 5. sink.handle(decision)
```

**گام ۲ همیشه قبل از Provider — در Validation و Live یکسان.**

## تفکیک سه لایه هوش

```
┌──────────────────────────────────────────────────────────┐
│  لایه ۳ — Decision Intelligence (Engine)                 │
│  "آیا این سیگنال با قوانین ریسک و شرایط بازار سازگار است؟" │
├──────────────────────────────────────────────────────────┤
│  لایه ۲ — Signal Intelligence (Providers)                │
│  "با این ویژگی‌ها چه نظری دارم؟"                          │
├──────────────────────────────────────────────────────────┤
│  لایه ۱ — Feature Intelligence (Feature Builder)       │
│  "بازار الان چه ویژگی‌هایی دارد؟"                       │
├──────────────────────────────────────────────────────────┤
│  لایه ۰ — Raw Data (MarketDataProvider)                  │
│  "قیمت و حجم چقدر است؟"                                 │
└──────────────────────────────────────────────────────────┘
```

## تست

| لایه | تست |
|------|-----|
| Feature Builder | `df` ثابت → `FeatureSet` ثابت (snapshot test) |
| Provider | `FeatureSet` mock → `StrategySignal` (بدون OHLCV) |
| Engine | `StrategySignal` mock → `Decision` (بدون feature) |

هر لایه **جدا** تست می‌شود.

## Anti-Patterns

| Anti-Pattern | درست |
|--------------|------|
| `import ta` داخل Provider | اندیکاتور در FeatureBuilder |
| Provider `df` می‌گیرد | Provider `FeatureSet` می‌گیرد |
| Engine خودش RSI محاسبه کند | Engine فقط `MarketContext` از Builder می‌گیرد |
| اندیکاتور hardcode در کد Provider | تعریف در `config/features.yaml` |

## جمع‌بندی

```
Feature Builder  = بازار را توصیف می‌کند
Signal Provider  = بازار را تفسیر می‌کند
Decision Engine  = تفسیر را تأیید یا رد می‌کند
```

سه لایه — سه مسئولیت — هیچ‌کدام جایگزین دیگری نیست.
