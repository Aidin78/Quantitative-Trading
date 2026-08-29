# Frontend

Next.js 14 dashboard for the Quantitative Trading Platform (Phase 6 — Observability).

## Pages

| Route             | Purpose                                                 |
| ----------------- | ------------------------------------------------------- |
| `/`               | Decision Monitor — live feed, stats, explainability     |
| `/decisions/[id]` | Full decision detail (features, market context, log)    |
| `/analytics`      | Decision trends, provider contribution, regime analysis |
| `/validation`     | Validation harness — **Backtest** + **Optimize** tabs   |
| `/research`       | **Hypotheses & Candidates** + **Experiments** tabs      |
| `/providers`      | Signal provider management                              |
| `/engine`         | Engine config (aggregation, filter, risk)               |
| `/market-data`    | OHLCV download / cache                                  |
| `/replay`         | Forensic replay by correlation ID                       |

`/optimization` and `/experiments` remain their own routes; the sidebar folds
each into its parent section via `components/layout/SectionTabs`.

## Development

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API defaults to `http://localhost:8000` (`NEXT_PUBLIC_API_URL`).

```bash
npm run lint    # ESLint + TypeScript
npm run build   # production build
```

See [`docs/frontend/`](../docs/frontend/) for stack and page specs.
