# Event Layer

> **تفکیک مفهومی:** این سند **مکانیزم انتشار** (EventBus، handlers) را توضیح می‌دهد.
> taxonomy، lifecycle و schema رسمی eventها در [event-model.md](./event-model.md) است.

## چرا Event Layer لازم است؟

در معماری فعلی چند خروجی هم‌زمان از یک cycle داریم:

- ثبت `DecisionRecord` در DB
- ارسال `decision.created` به Dashboard
- ارسال Telegram برای `approved` signals
- ثبت progress برای Validation
- alert برای خطاهای Live یا FeatureBuilder

اگر Runtime مستقیماً همه این side-effectها را صدا بزند، دوباره به coupling می‌رسیم:

```
❌ بدون Event Layer:

PlatformRuntime
  ├─ save decision to DB
  ├─ publish websocket
  ├─ send telegram
  ├─ update metrics
  └─ write validation progress
```

راه درست:

```
✅ با Event Layer:

PlatformRuntime
  └─ emit DomainEvent
        │
        ├─ DatabaseEventHandler
        ├─ WebSocketEventHandler
        ├─ TelegramEventHandler
        ├─ MetricsEventHandler
        └─ AlertEventHandler
```

## جایگاه در معماری

```
MarketDataProvider
      ↓
FeatureBuilder
      ↓
SignalProviders
      ↓
DecisionEngine
      ↓
PlatformRuntime
      ↓
EventBus.emit(DomainEvent)
      ↓
Event Handlers / API / Dashboard / Telegram
```

Event Layer بین **Runtime** و **Adapter/Presentation** قرار می‌گیرد.

## مسئولیت‌ها

### Event Layer انجام می‌دهد

| کار | توضیح |
|-----|--------|
| تعریف `DomainEvent` | eventهای استاندارد و type-safe |
| انتشار event | sync در MVP، Redis Streams/PubSub در production |
| fan-out | یک event به چند handler |
| جداسازی side-effect | Runtime فقط event تولید می‌کند |
| observability | هر event قابل log، trace و replay باشد |

### Event Layer انجام نمی‌دهد

| کار | چرا نه |
|-----|--------|
| تصمیم معاملاتی | فقط `DecisionEngine` |
| محاسبه indicator | فقط `FeatureBuilder` |
| تفسیر بازار | فقط `SignalProvider` |
| اجرای معامله | `ExecutionEngine` — نه Event Layer؛ Telegram فقط `SignalPublished` |

## Domain Events

Eventها در چهار خانواده طبقه‌بندی می‌شوند — جزئیات کامل در [event-model.md](./event-model.md):

| خانواده | نمونه event_type | Consumerها |
|---------|------------------|------------|
| **Market** | `CandleReceived`, `FeatureSetBuilt` | Feature Store، metrics |
| **Signal** | `ProviderOpinion`, `ProviderSkipped` | decision detail، analytics |
| **Decision** | `DecisionMade`, `DecisionApproved`, `DecisionRejected` | DB، WS، Risk |
| **Execution** | `OrderIntentCreated`, `FillReceived`, `PositionClosed` | execution + state |
| **Operational** | `ValidationProgressed`, `RuntimeCycleFailed` | progress، alerts |

`SignalPublished` (Telegram) در خانواده Execution است اما **notification** — نه trade. جزئیات: [execution-model.md](./execution-model.md).

همه eventها از `EventEnvelope` مشترک پیروی می‌کنند (`event_time`, `processing_time`, `correlation_id`, `causation_id`). معنای زمان: [time-semantics.md](./time-semantics.md).

## EventBus Interface

```python
class EventBus(Protocol):
    async def publish(self, event: EventEnvelope) -> None: ...
    async def publish_many(self, events: list[EventEnvelope]) -> None: ...

class EventHandler(Protocol):
    event_types: set[str]
    async def handle(self, event: EventEnvelope) -> None: ...
```

## پیاده‌سازی مرحله‌ای

| فاز | پیاده‌سازی | دلیل |
|-----|------------|------|
| MVP | `InMemoryEventBus` | ساده، قابل تست، بدون infra اضافه |
| Staging/Live | Redis Pub/Sub | مناسب WebSocket fan-out |
| Production جدی | Redis Streams یا Kafka | replay، durability، backpressure |

برای این پروژه، شروع با `InMemoryEventBus` + adapter برای Redis کافی است.

## Event Store

| نیاز | راهکار | فاز |
|------|--------|-----|
| مشاهده decisionها | جدول `decisions` | MVP |
| audit کامل event chain | جدول `event_log` | Phase 4 (validation) |
| strict replay | `event_log` + [Replay Engine](./replay-engine.md) | Phase 4+ |
| re-execute replay | event_log + [Feature Store](./feature-store.md) | Phase 6+ |

هر `DecisionEvent` باید `state_snapshot_id` و `correlation_id` داشته باشد — [state-management.md](./state-management.md).

## Runtime با Event Layer

```python
class PlatformRuntime:
    async def run_cycle(self, symbol: str, timeframe: str) -> Decision:
        df = await self.data_provider.get_latest(symbol, timeframe)
        features, context = self.feature_builder.build(df, symbol, timeframe)
        await self.feature_store.put(features)
        await self.event_bus.publish(envelope("FeatureSetBuilt", features))

        snapshot = self.state_store.snapshot(self.portfolio_id)
        provider_signals = []
        for provider in self.providers:
            signal = provider.analyze(features, context)
            provider_signals.append(signal)
            await self.event_bus.publish(envelope("ProviderOpinion", signal))

        decision = self.engine.process(provider_signals, context, snapshot)
        await self.event_bus.publish(envelope("DecisionMade", decision))

        if decision.result == "approved":
            await self.event_bus.publish(envelope("DecisionApproved", decision))
            exec_events = await self.execution_engine.execute(decision, snapshot)
            for ev in exec_events:
                await self.event_bus.publish(ev)
        else:
            await self.event_bus.publish(envelope("DecisionRejected", decision))

        return decision
```

مرز State/Risk: [state-risk-contract.md](./state-risk-contract.md).

## EventHandler Mapping

| event_type | Handler |
|------------|---------|
| `DecisionApproved` / `DecisionRejected` | `DatabaseEventHandler`, `WebSocketEventHandler` |
| `FillReceived` / `PositionClosed` | `DatabaseEventHandler`, `ExecutionLogHandler` |
| `SignalPublished` | `TelegramEventHandler` (فقط notification) |
| `ValidationProgressed` | `WebSocketEventHandler` |

## Anti-Patterns

| Anti-Pattern | درست |
|--------------|------|
| Runtime مستقیم Telegram بزند | `TelegramEventHandler` روی `SignalPublished` |
| WebSocket از DB polling کند | WebSocket handler event را push کند |
| Event بدون correlation_id | همه eventهای یک cycle باید قابل trace باشند |
| همه eventها durable از روز اول | MVP با InMemoryEventBus، بعد Redis Streams |
| Engine event publish کند | Engine pure بماند؛ Runtime event منتشر کند |

## جمع‌بندی

```
Decision Engine = تصمیم pure
Platform Runtime = orchestration
Event Layer = انتشار اتفاقات دامنه
Event Handlers = side-effectها
```

Event Layer باعث می‌شود سیستم هم real-time باشد، هم قابل audit، هم بدون coupling بین Runtime و خروجی‌ها.
