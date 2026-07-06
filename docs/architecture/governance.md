# Governance — Experiment Management

> مکانیزم رسمی برای tracking آزمایش‌ها، نسخه‌بندی config، مقایسه نتایج و A/B testing در سطح سیستم.
>
> مرتبط: [feature-store.md](./feature-store.md) | [replay-engine.md](./replay-engine.md) | [execution-model.md](./execution-model.md)

## مشکل بدون Governance

| وضعیت | پیامد |
|-------|--------|
| `engine.yaml` دستی عوض شود | نمی‌دانیم کدام config تصمیم را ساخت |
| دو validation پشت سر هم | مقایسه غیررسمی |
| provider جدید vs قدیم | بدون experiment tracking |
| live با config نامشخص | غیرقابل audit |

## اصل

هر **run** سیستم (validation، live session، replay job) باید به یک **Experiment** یا **ConfigRevision** قابل ردیابی bind شود.

```
ConfigRevision  →  Experiment  →  Run  →  Decisions / Events / Metrics
```

## مدل‌های اصلی

### ConfigRevision

نسخه immutable از تمام configهای مؤثر:

```python
@dataclass(frozen=True)
class ConfigRevision:
    revision_id: str                 # e.g. "rev_abc123"
    created_at: datetime
    engine_config_hash: str          # hash(engine.yaml)
    features_config_hash: str        # hash(features.yaml)
    providers_config_hash: str       # hash(merged providers/*.yaml)
    fill_model_id: str | None        # validation
    risk_limits_hash: str
    label: str                       # "baseline_v1", "aggressive_risk"
    parent_revision_id: str | None   # lineage
```

### Experiment

```python
@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    name: str
    description: str
    revision_id: str                   # ConfigRevision
    status: Literal["draft", "running", "completed", "archived"]
    mode: Literal["validation", "live", "paper", "replay"]
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    date_range: tuple[datetime, datetime] | None   # validation
    created_by: str
    tags: tuple[str, ...]
    hypothesis: str | None           # "lower min_confidence increases approval rate"
```

### ExperimentRun

یک اجرای concrete:

```python
@dataclass(frozen=True)
class ExperimentRun:
    run_id: str
    experiment_id: str
    revision_id: str
    started_at: datetime
    completed_at: datetime | None
    status: Literal["running", "completed", "failed", "cancelled"]
    metrics_summary: dict[str, float] | None
```

## Propagation — experiment_id در همه جا

هر artifact سیستم باید `experiment_id` و `revision_id` داشته باشد:

| Artifact | فیلدها |
|----------|--------|
| `EventEnvelope` | `experiment_id`, `revision_id` |
| `DecisionEvent` | `experiment_id`, `revision_id` |
| `FeatureSetRecord` | `revision_id` (features hash) |
| `OrderIntent` | `experiment_id` |
| `ValidationRun` / `BacktestRun` | `experiment_id`, `run_id` |

## A/B Testing

دو experiment موازی روی **همان داده** با revision متفاوت:

```
Experiment A (revision: baseline)
Experiment B (revision: high_confidence_threshold)
        │
        ▼
ComparisonReport
```

```python
@dataclass
class ExperimentComparison:
    experiment_a_id: str
    experiment_b_id: str
    metrics_delta: dict[str, float]   # approval_rate, sharpe, max_dd, ...
    decision_diff_count: int          # تعداد cycleهای با تصمیم متفاوت
    significant_cycles: list[str]     # correlation_ids
```

### اجرا

```bash
python scripts/run_experiment.py \
  --name "confidence_threshold_ab" \
  --revisions baseline,aggressive \
  --symbol BTC/USDT --from 2024-01-01 --to 2024-12-31
```

خروجی: دو `ExperimentRun` + `ComparisonReport`.

## Provider Versioning

هر Provider در experiment قابل version است:

```yaml
# config/providers/rsi_divergence.yaml
provider_id: rsi_divergence
version: v2
enabled: true
weight: 1.0
params:
  oversold: 28
```

`providers_config_hash` در `ConfigRevision` تغییر می‌کند → مقایسه experiment معنی‌دار می‌شود.

## Engine Config Lineage

```
rev_001 (baseline)
    │
    ├── rev_002 (min_confidence: 0.65 → 0.70)
    │       └── experiment: "conf_ab_test"
    │
    └── rev_003 (max_drawdown: 5 → 3)
            └── experiment: "tight_risk"
```

ذخیره در DB:

```sql
CREATE TABLE config_revisions (
    revision_id           VARCHAR(64) PRIMARY KEY,
    engine_config_hash    VARCHAR(64) NOT NULL,
    features_config_hash  VARCHAR(64) NOT NULL,
    providers_config_hash VARCHAR(64) NOT NULL,
    fill_model_id         VARCHAR(50),
    label                 VARCHAR(100),
    parent_revision_id    VARCHAR(64),
    config_bundle         JSONB NOT NULL,    -- snapshot کامل yamlها
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE experiments (
    experiment_id     VARCHAR(64) PRIMARY KEY,
    revision_id       VARCHAR(64) REFERENCES config_revisions(revision_id),
    name              VARCHAR(200) NOT NULL,
    status            VARCHAR(20) NOT NULL,
    mode              VARCHAR(20) NOT NULL,
    hypothesis        TEXT,
    tags              TEXT[],
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE experiment_runs (
    run_id            VARCHAR(64) PRIMARY KEY,
    experiment_id     VARCHAR(64) REFERENCES experiments(experiment_id),
    status            VARCHAR(20) NOT NULL,
    metrics_summary   JSONB,
    started_at        TIMESTAMPTZ NOT NULL,
    completed_at      TIMESTAMPTZ
);
```

## API

| Endpoint | توضیح |
|----------|--------|
| `POST /experiments` | ایجاد experiment |
| `GET /experiments` | لیست |
| `GET /experiments/{id}` | جزئیات + runs |
| `POST /experiments/{id}/runs` | شروع validation run |
| `GET /experiments/compare?a=&b=` | ComparisonReport |
| `GET /config/revisions` | lineage |
| `GET /config/revisions/{id}` | bundle کامل |

## Dashboard

صفحه **Experiments** (کنار Validation):

- لیست experimentها با status
- مقایسه side-by-side دو run
- drill-down به `decision_diff` per correlation_id
- لینک به Replay forensic

## تعامل با Replay

Re-execute replay با `revision_id` مشخص:

```
replay(cycle_id, revision_id=rev_002)  → DecisionDiff vs recorded (rev_001)
```

## Live Governance

قبل از live:

1. experiment باید `status=completed` در validation داشته باشد
2. `revision_id` در live runtime ثابت — تغییر config = experiment جدید
3. paper mode = experiment با `mode=paper`

```python
class LiveGovernanceGate:
    def allow_start(self, revision_id: str) -> bool:
        return self.experiment_store.has_successful_validation(revision_id)
```

## Anti-Patterns

| Anti-Pattern | درست |
|--------------|------|
| تغییر yaml بدون revision جدید | هر تغییر → `ConfigRevision` |
| مقایسه دستی دو CSV | `ExperimentComparison` API |
| live بدون experiment_id در events | propagation اجباری |
| A/B روی live بدون paper | ابتدا validation روی همان revisionها |

## فازبندی

| فاز | قابلیت |
|-----|--------|
| MVP | `revision_id` در event_log و decisions |
| v2 | Experiment + ExperimentRun + CLI |
| v3 | Comparison API + dashboard |
| v4 | LiveGovernanceGate + A/B automation |
