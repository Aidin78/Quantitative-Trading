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
                    │   Decision Engine   │  ← قلب سیستم
                    │  (تصمیم نهایی)      │
                    └──────────┬──────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
    ┌──────▼──────┐    ┌───────▼───────┐   ┌──────▼──────┐
    │  Providers  │    │ Market Context │   │  Portfolio  │
    │ (Strategies)│    │   (Data)       │   │   State     │
    └─────────────┘    └────────────────┘   └─────────────┘
           │
    ┌──────┴──────┬──────────────┐
    │             │              │
 EMA Cross    RSI Div       Strategy N
 (plug-in)    (plug-in)     (plug-in)
```

## لایه‌های معماری (از درون به بیرون)

### لایه ۱ — Decision Core (ثابت)

تغییر نمی‌کند مگر با تصمیم آگاهانه معماری:

| جزء | مسئولیت |
|-----|----------|
| `DecisionEngine` | orchestration pipeline |
| `MarketFilter` | آیا اصلاً شرایط معامله هست؟ |
| `Aggregator` | ترکیب نظر Providers |
| `RiskManager` | آیا این تصمیم مجاز است؟ |
| `DecisionLog` | ثبت شفاف هر مرحله |

**خروجی:** `Decision` (approved → `FinalSignal` | rejected → `RejectionReason`)

### لایه ۲ — Runtime (محیط اجرا)

Engine را در یک **چرخه تصمیم** اجرا می‌کند. Backtest و Live هر دو **همان Runtime** هستند:

| جزء | نقش |
|-----|-----|
| `PlatformRuntime` | حلقه اصلی: data → providers → engine → sink |
| `MarketDataProvider` | تأمین OHLCV + context |
| `SignalProvider` | interface استراتژی‌ها |
| `DecisionSink` | مقصد خروجی تصمیم |

```
PlatformRuntime
    │
    ├─ fetch market data
    ├─ build MarketContext
    ├─ call all SignalProviders → list[StrategySignal]
    ├─ DecisionEngine.process() → Decision
    └─ DecisionSink.handle(decision)
```

### لایه ۳ — Adapters (قابل تعویض)

| Adapter | Backtest | Live |
|---------|----------|------|
| `MarketDataProvider` | CSVProvider | LiveProvider (ccxt) |
| `DecisionSink` | SimulatedTradeSink | TelegramSink + DBSink + WSSink |
| `Scheduler` | iterate تاریخ | APScheduler |

**Engine و Runtime تغییر نمی‌کنند — فقط adapter عوض می‌شود.**

### لایه ۴ — Providers (plug-in)

استراتژی = یک `SignalProvider`:

```python
class SignalProvider(Protocol):
    provider_id: str
    weight: float
    enabled: bool

    def analyze(self, df: pd.DataFrame,
                context: MarketContext) -> StrategySignal: ...
```

افزودن استراتژی جدید = implement کردن protocol + register — **بدون لمس Engine**.

### لایه ۵ — Presentation (مشاهده‌پذیری)

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
├── context.py         # MarketContext, PortfolioState
├── provider.py        # SignalProvider protocol
├── data.py            # MarketDataProvider protocol
└── sink.py            # DecisionSink protocol
```

تغییر contract = نسخه‌گذاری (`v1`, `v2`) — نه patch بی‌برنامه.

## Anti-Patterns (اجتناب کنید)

| Anti-Pattern | چرا اشتباه است |
|--------------|----------------|
| استراتژی مستقیماً Telegram صدا بزند | دور زدن Engine |
| BacktestRunner جدا از LiveRunner با logic متفاوت | شکستن «یک موتور، دو حالت» |
| Risk check داخل استراتژی | پراکندگی قوانین |
| Dashboard اول صفحه Strategies | تمرکز روی peripheral، نه core |
| تست فقط روی PnL استراتژی تکی | Engine بدون integration test می‌ماند |

## جمع‌بندی

```
Feature-Driven:  "بیایید یک استراتژی EMA بسازیم و بک‌تست کنیم"
Architecture-Driven: "بیایید Engine را بسازیم، با Mock Provider تست کنیم،
                     Runtime را وصل کنیم، بعد Providerها plug-in شوند"
```

محصول نهایی یک **پلتفرم تصمیم‌گیری** است که استراتژی‌ها در آن اجرا می‌شوند — نه مجموعه‌ای از استراتژی‌ها با یک UI.
