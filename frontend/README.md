# Frontend

Next.js 14 dashboard for the Quantitative Trading Platform (Phase 6 — Observability).

## Pages

| Route         | Purpose                                             |
| ------------- | --------------------------------------------------- |
| `/`           | Decision Monitor — live feed, stats, explainability |
| `/engine`     | Engine config (aggregation, filter, risk)           |
| `/replay`     | Forensic replay by correlation ID                   |
| `/signals`    | Approved decisions                                  |
| `/validation` | Run validation harness                              |
| `/providers`  | Signal provider management                          |

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
