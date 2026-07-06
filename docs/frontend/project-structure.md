# ساختار پروژه فرانت‌اند

## درخت پوشه‌ها

```
frontend/
├── app/
│   ├── globals.css
│   ├── layout.tsx                 # root layout (providers)
│   ├── (auth)/
│   │   ├── layout.tsx
│   │   └── login/
│   │       └── page.tsx
│   └── (dashboard)/
│       ├── layout.tsx             # sidebar + header
│       ├── page.tsx               # Decision Monitor
│       ├── signals/
│       │   ├── page.tsx
│       │   └── [id]/
│       │       └── page.tsx
│       ├── providers/
│       │   ├── page.tsx
│       │   └── [id]/
│       │       └── page.tsx
│       ├── features/
│       │   └── page.tsx
│       ├── validation/
│       │   ├── page.tsx
│       │   └── results/
│       │       └── [id]/
│       │           └── page.tsx
│       ├── live/
│       │   └── page.tsx
│       ├── analytics/
│       │   └── page.tsx
│       ├── risk/
│       │   └── page.tsx
│       └── settings/
│           └── page.tsx
├── components/
│   ├── ui/                        # shadcn components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── table.tsx
│   │   ├── dialog.tsx
│   │   ├── badge.tsx
│   │   ├── select.tsx
│   │   ├── input.tsx
│   │   └── ...
│   ├── layout/
│   │   ├── sidebar.tsx
│   │   ├── header.tsx
│   │   ├── live-status-badge.tsx
│   │   └── page-header.tsx
│   ├── charts/
│   │   ├── candlestick-chart.tsx
│   │   ├── equity-curve.tsx
│   │   ├── drawdown-chart.tsx
│   │   ├── strategy-performance-chart.tsx
│   │   └── monthly-heatmap.tsx
│   ├── decisions/
│   │   ├── decision-feed.tsx
│   │   ├── decision-log.tsx
│   │   ├── rejection-breakdown.tsx
│   │   └── provider-votes.tsx
│   ├── signals/
│   │   ├── signal-table.tsx
│   │   ├── signal-filters.tsx
│   │   ├── signal-detail-card.tsx
│   │   ├── signal-feed.tsx
│   │   └── signal-side-badge.tsx
│   ├── providers/
│   │   ├── provider-card.tsx
│   │   ├── provider-list.tsx
│   │   └── provider-params-form.tsx
│   ├── features/
│   │   ├── feature-config-editor.tsx
│   │   └── feature-snapshot.tsx
│   ├── validation/
│   │   ├── validation-form.tsx
│   │   ├── validation-progress.tsx
│   │   ├── engine-metrics.tsx
│   │   ├── outcome-metrics.tsx
│   │   └── validation-comparison.tsx
│   ├── live/
│   │   ├── live-monitor.tsx
│   │   ├── decision-log.tsx
│   │   └── live-controls.tsx
│   ├── analytics/
│   │   ├── overview-stats.tsx
│   │   └── performance-breakdown.tsx
│   └── risk/
│       ├── risk-rules-card.tsx
│       └── risk-gauge.tsx
├── hooks/
│   ├── use-signals.ts
│   ├── use-decisions.ts
│   ├── use-providers.ts
│   ├── use-features.ts
│   ├── use-validation.ts
│   ├── use-live-status.ts
│   ├── use-websocket.ts
│   └── use-market-data.ts
├── lib/
│   ├── api-client.ts
│   ├── api-types.ts               # generated or manual
│   ├── utils.ts                   # cn(), formatters
│   ├── constants.ts
│   └── formatters.ts              # price, percent, date
├── stores/
│   ├── ui-store.ts                # sidebar, theme
│   └── filter-store.ts            # table filters
├── providers/
│   ├── query-provider.tsx         # React Query
│   ├── theme-provider.tsx
│   └── websocket-provider.tsx
├── public/
│   └── ...
├── tailwind.config.ts
├── components.json                # shadcn config
├── next.config.ts
├── tsconfig.json
├── package.json
├── Dockerfile
└── .env.example
```

## Layout Hierarchy

```
app/layout.tsx (Root)
├── ThemeProvider
├── QueryProvider
└── WebSocketProvider
    │
    └── (dashboard)/layout.tsx
        ├── Sidebar
        ├── Header
        │   └── LiveStatusBadge
        └── {children}  ← page content
```

## کامپوننت‌های کلیدی

### Sidebar

```typescript
const navItems = [
  { href: '/', label: 'Decisions', icon: LayoutDashboard },
  { href: '/signals', label: 'Signals', icon: Zap },
  { href: '/providers', label: 'Providers', icon: Brain },
  { href: '/features', label: 'Features', icon: SlidersHorizontal },
  { href: '/validation', label: 'Validation', icon: FlaskConical },
  { href: '/live', label: 'Live', icon: Radio },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/risk', label: 'Risk', icon: Shield },
  { href: '/settings', label: 'Settings', icon: Settings },
];
```

### CandlestickChart

- ورودی: `OHLCV[]` + optional `markers[]` (entry, SL, TP)
- کتابخانه: Lightweight Charts
- responsive با `ResizeObserver`

### SignalTable

- TanStack Table
- ستون‌ها: time, symbol, side, entry, SL, TP, confidence, providers, status
- sort + filter + pagination
- row click → `/signals/[id]`
- برای rejectedها از `DecisionFeed` و `/decisions/{id}` استفاده شود؛ `SignalTable` فقط approved decisions را نشان می‌دهد.

## Hooks

### useSignals

```typescript
export function useSignals(filters: SignalFilters) {
  return useQuery({
    queryKey: ['signals', filters],
    queryFn: () => api.getSignals(filters),
    refetchInterval: 60_000, // fallback polling
  });
}
```

### useWebSocket

```typescript
export function useSignalFeed() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws/signals`);
    ws.onmessage = (event) => {
      const signal = JSON.parse(event.data);
      queryClient.invalidateQueries({ queryKey: ['signals'] });
      toast.success(`New ${signal.side} signal: ${signal.symbol}`);
    };
    return () => ws.close();
  }, []);
}
```

## Providers

### QueryProvider

```typescript
'use client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 2 },
  },
});

export function QueryProvider({ children }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
```

## Formatters

```typescript
// lib/formatters.ts
export const formatPrice = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2 });

export const formatPercent = (n: number) =>
  `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;

export const formatDate = (d: string) =>
  format(new Date(d), 'yyyy-MM-dd HH:mm');
```

## قرارداد نام‌گذاری

| نوع | قرارداد | مثال |
|-----|---------|------|
| فایل کامپوننت | kebab-case | `signal-table.tsx` |
| کامپوننت React | PascalCase | `SignalTable` |
| Hook | camelCase با use | `useSignals` |
| Store | camelCase | `useUIStore` |
| Type/Interface | PascalCase | `FinalSignal` |
| Constant | UPPER_SNAKE | `API_BASE_URL` |

## shadcn/ui Setup

```bash
npx shadcn@latest init
npx shadcn@latest add button card table dialog badge select input tabs
```
