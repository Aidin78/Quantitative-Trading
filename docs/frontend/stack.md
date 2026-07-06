# Frontend Stack

## Framework و زبان

| مورد | انتخاب | نسخه |
|------|--------|------|
| Framework | Next.js (App Router) | 14+ |
| زبان | TypeScript | 5.x |
| Node | LTS | 20+ |
| Package Manager | pnpm یا npm | — |

## کتابخانه‌های UI

| کتابخانه | کاربرد |
|----------|--------|
| **Tailwind CSS** | استایل‌دهی |
| **shadcn/ui** | کامپوننت‌های پایه (Button, Table, Dialog, ...) |
| **Radix UI** | زیرساخت accessibility (از طریق shadcn) |
| **lucide-react** | آیکون‌ها |
| **next-themes** | Dark/Light mode |
| **class-variance-authority** | variant classes (با shadcn) |
| **tailwind-merge** | ادغام class names |

## State Management

| کتابخانه | کاربرد |
|----------|--------|
| **TanStack Query (React Query)** | server state — API data, cache, refetch |
| **Zustand** | client state — filters, UI preferences, sidebar |

```typescript
// مثال: server state
const { data: decisions } = useQuery({
  queryKey: ['decisions', filters],
  queryFn: () => api.getDecisions(filters),
});

// مثال: client state
const { filters, setFilters } = useDecisionFilters();
```

## چارت‌ها

| کتابخانه | کاربرد |
|----------|--------|
| **Lightweight Charts** (TradingView) | کندل‌استیک، volume، markers سیگنال |
| **Recharts** | equity curve، drawdown، bar charts |
| **ECharts** (اختیاری) | heatmap، نمودارهای پیچیده |

## جداول

| کتابخانه | کاربرد |
|----------|--------|
| **TanStack Table** | sort, filter, pagination, column visibility |

## فرم‌ها

| کتابخانه | کاربرد |
|----------|--------|
| **React Hook Form** | مدیریت فرم |
| **Zod** | validation schema |
| **@hookform/resolvers** | اتصال Zod به RHF |

## Real-time

| کتابخانه | کاربرد |
|----------|--------|
| Native **WebSocket** یا **socket.io-client** | decision stream، validation progress |

## اعلان‌ها

| کتابخانه | کاربرد |
|----------|--------|
| **Sonner** | toast notifications |

## Auth

| گزینه | کاربرد |
|-------|--------|
| **NextAuth.js** | self-hosted auth |
| **Clerk** | managed auth (سریع‌تر برای MVP) |

## ابزارهای توسعه

| ابزار | کاربرد |
|-------|--------|
| **ESLint** | lint |
| **Prettier** | format |
| **openapi-typescript** | generate types از OpenAPI بک‌اند |

## package.json (وابستگی‌های اصلی)

```json
{
  "dependencies": {
    "next": "^14.2",
    "react": "^18.3",
    "react-dom": "^18.3",
    "@tanstack/react-query": "^5.60",
    "@tanstack/react-table": "^8.20",
    "zustand": "^5.0",
    "lightweight-charts": "^4.2",
    "recharts": "^2.13",
    "react-hook-form": "^7.53",
    "zod": "^3.23",
    "@hookform/resolvers": "^3.9",
    "sonner": "^1.7",
    "next-themes": "^0.4",
    "date-fns": "^4.1",
    "lucide-react": "^0.460",
    "class-variance-authority": "^0.7",
    "clsx": "^2.1",
    "tailwind-merge": "^2.5"
  },
  "devDependencies": {
    "typescript": "^5.6",
    "tailwindcss": "^3.4",
    "@types/react": "^18.3",
    "eslint": "^8.57",
    "prettier": "^3.3",
    "openapi-typescript": "^7.4"
  }
}
```

## Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXTAUTH_SECRET=...
NEXTAUTH_URL=http://localhost:3000
```

## طراحی بصری

| جنبه | مقدار |
|------|-------|
| تم پیش‌فرض | Dark |
| رنگ صعودی (BUY) | `#22c55e` (green-500) |
| رنگ نزولی (SELL) | `#ef4444` (red-500) |
| رنگ HOLD / neutral | `#6b7280` (gray-500) |
| فونت UI | Inter |
| فونت اعداد | JetBrains Mono |
| Border radius | 0.5rem (shadcn default) |
| Sidebar width | 256px |

## API Client

```typescript
// lib/api-client.ts
const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export const api = {
  getDecisions: (params: DecisionFilters) =>
    fetch(`${BASE_URL}/api/v1/decisions?${qs(params)}`).then(r => r.json()),

  runValidation: (config: ValidationConfig) =>
    fetch(`${BASE_URL}/api/v1/validation/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }).then(r => r.json()),
};
```

## Type Sync با بک‌اند

```bash
# generate types from OpenAPI
npx openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts
```

یا تعریف دستی در `lib/types.ts` مطابق Pydantic models.

## ساختار Routing (App Router)

| Route | صفحه |
|-------|------|
| `/` | Decision Monitor |
| `/signals` | لیست سیگنال‌ها |
| `/signals/[id]` | جزئیات سیگنال |
| `/providers` | مدیریت SignalProviderها |
| `/providers/[id]` | جزئیات Provider |
| `/features` | Feature Config و آخرین FeatureSet |
| `/validation` | اجرای Validation |
| `/validation/results/[id]` | نتایج Validation |
| `/live` | مانیتور لایو |
| `/analytics` | تحلیل عمیق |
| `/risk` | مدیریت ریسک |
| `/settings` | تنظیمات |
| `/login` | ورود |
