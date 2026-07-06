# قراردادها و استانداردها (Conventions)

## Git

### Branch Naming

```
main              # production-ready
develop           # integration branch
feature/xxx       # feature جدید
fix/xxx           # bug fix
docs/xxx          # مستندات
refactor/xxx      # refactoring
```

### Commit Messages

فرمت: `type(scope): description`

```
feat(engine): add weighted confidence aggregation
fix(backtest): correct SL hit detection on same candle
docs(api): add signals endpoint examples
refactor(strategies): extract indicator helpers
test(engine): add risk manager edge cases
chore(deps): upgrade fastapi to 0.115
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`

### Pull Request

- عنوان واضح
- توضیح کوتاه + test plan
- لینک به issue (در صورت وجود)
- حداقل 1 review قبل از merge

---

## Python (Backend)

### Style

- **Formatter/Linter:** ruff
- **Line length:** 100
- **Imports:** isort via ruff
- **Type hints:** اجباری برای public functions
- **Docstrings:** فقط برای logic غیر obvious

### مثال

```python
def aggregate_signals(
    signals: list[StrategySignal],
    min_agreeing: int = 2,
) -> AggregatedResult | None:
    """Combine strategy signals into consensus."""
    active = [s for s in signals if s.side != "HOLD"]
    ...
```

### Testing

- فایل تست: `test_<module>.py`
- نام تست: `test_<behavior>_<condition>`
- Fixtures در `conftest.py`
- حداقل coverage برای `engine/` و `strategies/`

```python
def test_risk_manager_rejects_when_daily_drawdown_exceeded():
    manager = RiskManager(max_daily_drawdown_pct=5.0)
    state = PortfolioState(daily_drawdown_pct=6.0, ...)
    result = manager.validate(signal, state)
    assert not result.passed
    assert result.reason == "daily_drawdown_limit"
```

### Error Handling

- Custom exceptions از `core/exceptions.py`
- API layer: تبدیل exception به HTTP status
- هرگز bare `except:` — همیشه specific

---

## TypeScript (Frontend)

### Style

- **Linter:** ESLint
- **Formatter:** Prettier
- **Strict mode:** enabled در tsconfig
- **Components:** functional only
- **Exports:** named exports (به‌جز page.tsx)

### مثال

```typescript
interface SignalTableProps {
  signals: FinalSignal[];
  onRowClick: (id: string) => void;
}

export function SignalTable({ signals, onRowClick }: SignalTableProps) {
  ...
}
```

### File Organization

- یک component per file
- Co-locate types اگر فقط در همان فایل استفاده می‌شوند
- Shared types در `lib/api-types.ts`

---

## API Design

### Versioning

- Prefix: `/api/v1/`
- Breaking changes → `/api/v2/`

### Response Format

لیست‌ها:

```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "limit": 50,
  "pages": 2
}
```

تک آیتم: object مستقیم

### Status Codes

| Code | کاربرد |
|------|--------|
| 200 | موفق |
| 201 | ایجاد شد |
| 202 | accepted (async job) |
| 400 | validation error |
| 401 | unauthorized |
| 403 | forbidden |
| 404 | not found |
| 422 | pydantic validation |
| 500 | server error |

### Dates

- همیشه UTC
- ISO 8601: `2026-07-06T10:30:00Z`
- Frontend: تبدیل به timezone کاربر برای نمایش

---

## Database

### Naming

| نوع | قرارداد | مثال |
|-----|---------|------|
| Table | snake_case, plural | `signals`, `backtest_runs` |
| Column | snake_case | `entry_price`, `created_at` |
| Index | `ix_<table>_<column>` | `ix_signals_timestamp` |
| FK | `fk_<table>_<ref_table>` | `fk_trades_signals` |

### Migrations

- هر تغییر schema → یک migration
- نام: `YYYYMMDD_description.py`
- هرگز edit migration اجراشده — migration جدید بسازید

---

## Config

### Secrets

- فقط در `.env` — هرگز در YAML یا code
- `.env` در `.gitignore`
- `.env.example` با placeholder (بدون مقدار واقعی)

### YAML Config

- `config/settings.yaml` — تنظیمات غیرحساس
- `config/risk.yaml` — قوانین ریسک
- `config/strategies/*.yaml` — پارامتر استراتژی‌ها

---

## Logging

### Backend

```python
import structlog
logger = structlog.get_logger()

logger.info("signal_generated", signal_id=sig.id, symbol=sig.symbol)
logger.warning("risk_rejected", reason=result.reason)
logger.error("exchange_api_failed", error=str(e), retry=attempt)
```

### سطوح

| Level | کاربرد |
|-------|--------|
| DEBUG | جزئیات development |
| INFO | رویدادهای عادی (signal, backtest complete) |
| WARNING | risk reject, retry |
| ERROR | API fail, exception |

### Frontend

- `console.error` فقط در development
- Production: Sentry یا مشابه

---

## Security

- API keys در env
- JWT expiry: 60 دقیقه
- Password: bcrypt hash
- CORS: فقط domain مجاز
- Rate limit: 100 req/min per IP (API)
- Input validation: Pydantic (backend) + Zod (frontend)

---

## Documentation

- تغییرات API → به‌روزرسانی `docs/api/`
- feature جدید → به‌روزرسانی roadmap اگر در scope
- README هر package: نحوه run و test

---

## Code Review Checklist

- [ ] Type hints / TypeScript types
- [ ] Tests برای logic جدید
- [ ] No secrets in code
- [ ] Error handling مناسب
- [ ] Consistent naming
- [ ] No look-ahead bias (backtest)
- [ ] Docs به‌روز اگر API تغییر کرده
