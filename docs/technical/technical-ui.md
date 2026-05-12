# Rentivo Web UI — Technical Documentation

Repository: `rentivo-ui` — [github.com/AnnVatlina/rentivo-ui](https://github.com/AnnVatlina/rentivo-ui)  
Deployed to: **GitHub Pages** — `https://annvatlina.github.io/rentivo-ui/`

---

## Tech Stack

| Concern | Library / Tool |
|---|---|
| Framework | React 18 + Vite 5 + TypeScript |
| Styling | Tailwind CSS 3 |
| UI components | shadcn/ui (Radix primitives + CSS variables) |
| Charts | Recharts |
| Server state / caching | TanStack Query v5 |
| Routing | React Router v6 (BrowserRouter + basename) |
| Forms + validation | React Hook Form + Zod |
| HTTP client | Axios with interceptors (auto-refresh JWT) |
| Exchange rates | open.er-api.com (free, no key, 24h cache via React Query) |
| Icons | Lucide React |
| Notifications | Sonner (toast) |
| CI/CD | GitHub Actions → GitHub Pages |

---

## Environment Variables

```
VITE_API_URL=https://rentivo-api-production.up.railway.app
VITE_BASE_PATH=/rentivo-ui/
```

`VITE_API_URL` is set as a **Variable** (not Secret) in the GitHub repository settings under Settings → Secrets and variables → Actions → Variables tab. `VITE_BASE_PATH` is hardcoded in the workflow.

---

## Themes

Three themes switchable from the Settings page, persisted in `localStorage`:

| Theme | CSS selector | Description |
|---|---|---|
| Indigo | `[data-theme="indigo"]` | Default — indigo primary, green income, red expense |
| Neutral | `[data-theme="neutral"]` | Greyscale primary, same income/expense colors |
| Dark | `[data-theme="dark"]` | Dark background, adjusted sidebar gradient |

Theme is applied via `data-theme` attribute on `<html>`. Colors are CSS custom properties (`--primary`, `--income`, `--expense`, `--sidebar-from`, `--sidebar-to`). Recharts reads colors at render time via `getComputedStyle` — wrapped in `useMemo` keyed on the current theme.

---

## JWT Token Management

- `access_token` stored in memory (module-level variable in `src/api/client.ts`) — XSS-safe.
- `refresh_token` stored in `localStorage`.
- Axios request interceptor calls `POST /auth/refresh` on 401 and retries the original request transparently.
- **Single-flight refresh**: a module-level promise prevents duplicate refresh calls when multiple requests 401 simultaneously.
- On logout: clear both tokens and redirect to `/login`.

---

## Routing

```
/login                    → Login (public)
/register                 → Register (public)
/                         → Dashboard (protected)
/deposits                 → Deposits list
/deposits/new             → New deposit form
/deposits/:id             → Edit deposit form
/subscriptions            → Subscriptions list
/subscriptions/new        → New subscription form
/subscriptions/:id        → Edit subscription form
/properties               → Properties list
/properties/new           → New property form
/properties/:id           → Property detail (transactions)
/properties/:id/edit      → Edit property form
/analytics                → Analytics charts
/import-export            → Export / Import
/settings                 → Settings
```

`BrowserRouter` with `basename={import.meta.env.BASE_URL}` handles GitHub Pages SPA routing. A `public/404.html` encodes the path into a query string on 404; `index.html` decodes it back via `history.replaceState`.

---

## Pages

### Dashboard (`/`)
Summary cards: total deposit balance, accrued interest, active subscriptions monthly cost, net this month. Module-gated cards hidden when the module is off.

### Deposits (`/deposits`)
- Full table: Title, Bank, Amount, Rate (with compound badge), Close date, Days elapsed, Accrued income.
- **Status coloring**: active (green dot), expiring ≤30 days (amber row + badge showing days left), expired (muted row + Expired badge).
- **Sorting** on all columns — click header to sort asc/desc, click again to reverse.
- **Pagination**: 10 per page, client-side. Sort reset resets to page 1.
- Summary in header: "N active · M expiring soon · K expired".

### Subscriptions (`/subscriptions`)
- Filter tabs: All / Active / One-time / Cancelled — with counts.
- **Sorting**: not on this page (subscriptions are ordered by next payment).
- **Pagination**: 10 per page.
- **Next payment** column: amber badge for payments ≤7 days away (shows `today` or `Nd`); blue badge for payments this calendar month (> 7 days away).
- Header subtitle: "N payments this month" pill when applicable.
- Monthly total in header counts **only `monthly` billing cycle** subscriptions (not prorated yearly/quarterly).

### Analytics (`/analytics`)
- **Year stepper**: ← 2026 → (chevron arrows, not dropdown).
- **Currency selector**: dropdown — selects the display currency for both charts.
- **Main chart** (deposits + subscriptions): bar chart, 12 months. Projected months shown at 30% opacity. Deposit income (green) and subscription expenses (red) bars side by side. Exchange rates applied via `deposit_currency` / `subscription_currency` from API response.
- **Property chart**: second card below, separate bar chart showing property income + expenses by month. Property selector dropdown in the card header. Shares the year stepper and currency selector with the main chart. Exchange rates applied from `propNativeCurrency` → selected currency.
- Summary cards below main chart: Income earned, Subs spent, Net (actual), Net (full year incl. projected).

### Properties (`/properties`)
- Table: Name, Address, Purchased, Price, Status badge (Active/Sold).
- **Click row** → opens `/properties/:id` (transactions view).
- **Gear icon** in last column → opens `/properties/:id/edit`.

### Property Detail (`/properties/:id`)
- **Full-width** layout (no max-width constraint).
- **4 summary cards**: Total invested · Expenses · Income received · Profit/Status.
  - Expenses and Income cards sum **all transactions regardless of currency** and convert to `default_currency` via exchange rates. Loading indicator shown while rates fetch.
- **Toolbar**: type filter (All / Expenses / Income) + category chip filters (only categories with data shown) + Reset button + Add button.
- **Table**: Category, Title, Amount, `{defaultCurrency}` (converted amount), Cycle, Date — all columns sortable.
- **tfoot**: Total expenses row (red) + Total income row (green) for all filtered rows (not just current page). Amount column groups by currency; base column shows converted total.
- **Pagination**: 20 per page, sorted newest-first by default.
- **Add/Edit form**: inline above table, compact 2-row grid. Category is a dropdown (not free text).

### Property Edit (`/properties/:id/edit`)
- Form: Name, Address, Purchase price, Currency, Purchase date, Status.
- Sold status reveals: Sale date, Sale price, Notes.
- Delete property button (with confirmation).
- Back button returns to `/properties/:id`.

### Import / Export (`/import-export`)
- Export button → downloads ZIP with 4 CSVs.
- Import dropzone — accepts ZIP or single CSV. Shows result counts (created / skipped per type).

### Settings (`/settings`)
- Default currency selector.
- Module toggles: Deposits, Subscriptions, Property.
- Theme selector: Indigo / Neutral / Dark.
- Demo data: Load / Delete all data.

---

## Exchange Rate Conversion

Exchange rates are fetched from `https://open.er-api.com/v6/latest/{baseCurrency}` (free, no API key, supports 160+ currencies including GEL).

```typescript
// src/api/exchangeRates.ts
export function useExchangeRates(baseCurrency: string) {
  return useQuery({
    queryKey: ['exchangeRates', baseCurrency],
    queryFn: () => fetchRates(baseCurrency),
    staleTime:  24 * 60 * 60 * 1000,  // 24h cache
    gcTime:     48 * 60 * 60 * 1000,
  })
}

export function convertCurrency(amount, from, to, rates): number | null {
  if (from === to) return amount
  if (rates[from] == null || rates[to] == null) return null
  return amount * (rates[to] / rates[from])
}
```

Used in:
- **PropertyDetail**: summary cards, per-row base currency column, tfoot totals.
- **Analytics**: main chart (deposit/subscription amounts), property chart.

---

## Pagination Component

`src/components/ui/pagination.tsx` exports:
- `<Pagination total perPage page onChange />` — renders "X–Y of N" + prev/page buttons/next with ellipsis. Returns `null` when `totalPages ≤ 1`.
- `paginate<T>(data, page, perPage): T[]` — returns the slice for the current page.

---

## API Layer

One file per resource in `src/api/`:

| File | Covers |
|---|---|
| `client.ts` | Axios instance, JWT interceptors, single-flight refresh |
| `auth.ts` | register, login, refresh |
| `deposits.ts` | CRUD |
| `subscriptions.ts` | CRUD |
| `properties.ts` | CRUD, transactions CRUD, getAnalytics |
| `settings.ts` | get, update, loadDemo, deleteData |
| `analytics.ts` | get (year + currency) |
| `exportImport.ts` | exportCsv, importCsv |
| `exchangeRates.ts` | useExchangeRates hook, convertCurrency utility |
| `types.ts` | All TypeScript interfaces matching API schemas |

---

## GitHub Actions / GitHub Pages Deployment

Workflow: `.github/workflows/pages.yml`

1. `npm ci` — install deps from lockfile.
2. `npx tsc -b` — TypeScript strict check (fails on any unused import or type error).
3. `vite build` — production build with `VITE_BASE_PATH=/rentivo-ui/` and `VITE_API_URL` from repo Variables.
4. Deploy `dist/` to `gh-pages` branch via `peaceiris/actions-gh-pages`.

SPA routing on GitHub Pages: `public/404.html` encodes the path into `?/path`; `index.html` script decodes it back via `history.replaceState` before React Router boots.
