# معماری Engine-Centric

## مشکل رویکرد Feature-Driven

در طراحی feature-driven، پروژه حول **قابلیت‌ها** چیده می‌شود:

```
استراتژی → Backtest → API → Live
```

این ترتیب باعث می‌شود:
- منطق تصمیم‌گیری پراکنده یا وابسته به استراتژی شود
- بک‌تست «محصول» به‌نظر برسد، نه «ابزار اعتبارسنجی»
- Live و Backtest به‌مرور از هم جدا شوند
- Dashboard حول استراتژی‌ها طراحی شود، نه تصمیم‌ها

## اصل محوری

**قلب پروژه Decision Engine است — نه استراتژی.**

استراتژی‌ها فقط **Signal Provider** هستند: منبعی که نظر تحلیلی با confidence برمی‌گرداند. هیچ استراتژی حق ندارد:
- مستقیماً سیگنال نهایی صادر کند
- قوانین ریسک را دور بزند
- مسیر Live/Backtest را تعیین کند

```
                    ┌─────────────────────┐
                    │   Decision Engine   │  ← لایه ۳: تصمیم
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Signal Providers  │  ← لایه ۲: نظر
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Feature Builder   │  ← لایه ۱: ویژگی/اندیکاتور
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  MarketDataProvider │  ← لایه ۰: OHLCV خام
                    └─────────────────────┘
```

استراتژی‌ها فقط **Signal Provider** هستند — نه محاسبه‌گر اندیکاتور، نه تصمیم‌گیر نهایی.

**زیرساخت مفهومی (کنار Engine):** Event Model، State Store، Feature Store، Replay Engine، Time Semantics — [overview.md](./overview.md).

## لایه‌های معماری (از درون به بیرون)

> جزئیات Feature Builder: [feature-builder.md](./feature-builder.md)

### لایه ۰ — Raw Data (Adapter)

| جزء | مسئولیت |
|-----|----------|
| `MarketDataProvider` | OHLCV خام — CSV یا Live API |

### لایه ۱ — Feature Builder (زیرساخت مشترک)

| جزء | مسئولیت |
|-----|----------|
| `FeatureBuilder` | OHLCV → `FeatureSet` + `MarketContext` |
| `FeatureRegistry` | تعریف declarative اندیکاتورها از YAML |

**خروجی:** `FeatureSet` (اندیکاتورها، flags، levels) + `MarketContext` (trend, volatility, session)

Provider و Engine هر دو از خروجی Builder تغذیه می‌شوند — نه از OHLCV خام.

### لایه ۲ — Signal Providers (plug-in)

استراتژی = `SignalProvider` — **تفسیر** `FeatureSet`، نه محاسبه اندیکاتور:

```python
class SignalProvider(Protocol):
    provider_id: str
    weight: float
    enabled: bool

    def analyze(self, features: FeatureSet,
                context: MarketContext) -> StrategySignal: ...
```

### لایه ۳ — Decision Core (قلب — ثابت)

| جزء | مسئولیت |
|-----|----------|
| `DecisionEngine` | orchestration pipeline |
| `MarketFilter` | از `MarketContext` — آیا شرایط معامله هست؟ |
| `Aggregator` | ترکیب نظر Providers |
| `RiskManager` | آیا این تصمیم مجاز است؟ |
| `DecisionLog` | ثبت شفاف هر مرحله |

**خروجی:** `Decision` (approved → `FinalSignal` | rejected → `RejectionReason`)

### لایه ۴ — Runtime (محیط اجرا)

Engine را در یک **چرخه تصمیم** اجرا می‌کند. Validation و Live هر دو **همان Runtime** هستند:

| جزء | نقش |
|-----|-----|
| `PlatformRuntime` | data → **features** → providers → engine → events |
| `MarketDataProvider` | تأمین OHLCV خام |
| `FeatureBuilder` | تأمین FeatureSet + MarketContext |
| `SignalProvider` | تفسیر features → نظر |
| `EventBus` | انتشار DomainEventها برای side-effectها |

```
PlatformRuntime
    │
    ├─ fetch OHLCV
    ├─ feature_builder.build(df) → FeatureSet + MarketContext
    ├─ StateStore.snapshot() → state_snapshot_id
    ├─ call all SignalProviders(features, context) → list[StrategySignal]
    ├─ DecisionEngine.process(signals, context, snapshot) → Decision
    ├─ ExecutionEngine.execute(decision, snapshot) → ExecutionEvents (validation)
    └─ EventBus.publish(EventEnvelope)
```

### لایه ۵ — Adapters (قابل تعویض)

| Adapter | Backtest | Live |
|---------|----------|------|
| `MarketDataProvider` | CSVProvider | LiveProvider (ccxt) |
| `EventBus` | InMemoryEventBus | Redis Pub/Sub یا Redis Streams |
| `EventHandlers` | Execution (simulated) + DB + event_log | DB + WS + Telegram |
| `Scheduler` | iterate تاریخ | APScheduler |

**Engine، Feature Builder و Runtime تغییر نمی‌کنند — فقط adapter عوض می‌شود.**

### لایه ۶ — Providers (plug-in)

جزئیات در لایه ۲ — اینجا فقط یادآوری: Provider آخرین لایه اضافه‌شونده است.

### لایه ۷ — Presentation (مشاهده‌پذیری)

Dashboard اول Decision را نشان می‌دهد، نه استراتژی را:
- Decision Log
- Rejection breakdown
- Engine config
- سپس Signals، سپس Providers

## Backtest = ابزار اعتبارسنجی Engine

بک‌تست **محصول نیست** — **ابزار سنجش کیفیت تصمیمات Engine** است.

| سؤال Feature-Driven | سؤال Engine-Centric |
|---------------------|---------------------|
| این استراتژی سودده است؟ | Engine با این قوانین چقدر درست تصمیم می‌گیرد؟ |
| Win rate استراتژی EMA چقدر است؟ | چند تصمیم reject شد و چرا؟ |
| کدام استراتژی بهتر است؟ | کدام ترکیب Providers + قوانین Risk بهترین outcome دارد؟ |

### معیارهای Engine (علاوه بر PnL)

| معیار | توضیح |
|-------|--------|
| **Approval Rate** | چند درصد تصمیم‌ها تأیید شد |
| **Rejection Breakdown** | دلایل رد (risk, filter, low confidence) |
| **Provider Contribution** | هر Provider چقدر در تصمیمات نهایی نقش داشت |
| **Decision Latency** | زمان پردازش (برای لایو) |
| **Outcome Quality** | PnL تصمیمات تأییدشده (نه کل استراتژی تکی) |

## قراردادهای ثابت (Contracts First)

قبل از هر Provider یا UI، این قراردادها freeze می‌شوند:

```
core/contracts/
├── signal.py          # StrategySignal, FinalSignal
├── decision.py        # Decision, RejectionReason, DecisionLog
├── features.py        # FeatureSet, FeatureBuilder protocol
├── context.py         # MarketContext, PortfolioState
├── provider.py        # SignalProvider protocol
├── data.py            # MarketDataProvider protocol
└── event.py           # DomainEvent, EventBus, EventHandler protocol
```

تغییر contract = نسخه‌گذاری (`v1`, `v2`) — نه patch بی‌برنامه.

## Anti-Patterns (اجتناب کنید)

| Anti-Pattern | چرا اشتباه است |
|--------------|----------------|
| استراتژی مستقیماً Telegram صدا بزند | دور زدن Engine |
| BacktestRunner جدا از LiveRunner با logic متفاوت | شکستن «یک موتور، دو حالت» |
| Risk check داخل استراتژی | پراکندگی قوانین |
| Dashboard اول صفحه Providers | تمرکز روی peripheral، نه core |
| اندیکاتور داخل Provider محاسبه شود | تکرار، ناهمسانی Validation/Live — در FeatureBuilder |
| Provider `df` بگیرد به‌جای `FeatureSet` | coupling به pandas — FeatureSet بده |

## جمع‌بندی

```
Feature-Driven:  "بیایید یک استراتژی EMA بسازیم و بک‌تست کنیم"
Architecture-Driven: "بیایید Engine را بسازیم، با Mock Provider تست کنیم،
                     Runtime را وصل کنیم، بعد Providerها plug-in شوند"
```

محصول نهایی یک **پلتفرم تصمیم‌گیری** است که استراتژی‌ها در آن اجرا می‌شوند — نه مجموعه‌ای از استراتژی‌ها با یک UI.
