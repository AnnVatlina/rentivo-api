# Rentivo Web UI — Technical Documentation

Repository: `rentivo-ui` (separate from the API repo)  
Deployed to: **Vercel** — zero-config for Vite, per-PR preview deployments, runtime env vars via dashboard.

---

## Tech Stack

| Concern | Library / Tool |
|---|---|
| Framework | React 18 + Vite + TypeScript |
| Styling | Tailwind CSS |
| UI components | shadcn/ui |
| Charts | Recharts |
| Server state / caching | TanStack Query v5 |
| Routing | React Router v7 |
| Forms + validation | React Hook Form + Zod |
| HTTP client | Axios with interceptors (auto-refresh JWT) |
| API types | openapi-typescript (generated from `/openapi.json`) |
| Linting / formatting | ESLint + Prettier |
| CI/CD | GitHub Actions → Vercel |

---

## Environment Variables

```
VITE_API_URL=https://your-api.railway.app
```

Set in Vercel dashboard per environment (preview / production). Never committed to the repository.

---

## API Type Generation

Run once after any backend change:

```bash
npx openapi-typescript $VITE_API_URL/openapi.json -o src/api/types.ts
```

Add this as a CI step to keep types in sync automatically.

---

## JWT Token Management

- `access_token` stored in memory (React context), not `localStorage` — XSS-safe.
- `refresh_token` stored in `localStorage`; Axios request interceptor calls `POST /auth/refresh` on 401 and retries the original request transparently.
- On logout: clear both tokens and redirect to `/login`.

---

## Pages

| Route | Page | Description |
|---|---|---|
| `/login` | **Login** | Email + password form. On success stores tokens and redirects to `/`. |
| `/register` | **Register** | Same form as login with confirm-password field. |
| `/` | **Dashboard** | Summary cards: total deposit balance, monthly subscription spend, net income this month. Sparkline charts per currency. |
| `/analytics` | **Analytics** | Year + currency selectors. Bar/line chart — deposit income vs subscription expenses per month. Toggle actual / projected. |
| `/deposits` | **Deposits** | Table of all deposits with columns: title, bank, amount, currency, rate, close date, accrued income. Sort by any column. |
| `/deposits/new` | **New deposit** | Form (all fields). Inline validation via Zod. |
| `/deposits/:id` | **Edit deposit** | Same form pre-filled. Delete button with confirmation dialog. |
| `/subscriptions` | **Subscriptions** | Table with filter tabs: All / Active / One-time / Cancelled. Columns: title, category, billing cycle, monthly cost, next payment. |
| `/subscriptions/new` | **New subscription** | Form with billing cycle selector that updates the monthly cost preview in real time. |
| `/subscriptions/:id` | **Edit subscription** | Same form pre-filled. Cancel (set inactive) and Delete actions. |
| `/import-export` | **Import / Export** | Export button → downloads ZIP. Import dropzone accepts ZIP or single CSV. Shows import result: created / skipped counts. |
| `/settings` | **Settings** | Change password form. (Placeholder for future: notification preferences, default currency.) |

---

## What Needs to Be Built

- [ ] Vite + React + TypeScript scaffold
- [ ] Tailwind CSS + shadcn/ui setup
- [ ] Axios instance with JWT interceptors (access token in memory, refresh logic)
- [ ] TanStack Query client + query key conventions
- [ ] React Router layout: public routes (login, register) vs protected routes (everything else)
- [ ] `AuthContext` — stores access token in memory, exposes `login()` / `logout()` / `user`
- [ ] API layer — one file per resource (`deposits.ts`, `subscriptions.ts`, etc.) wrapping Axios calls with generated types
- [ ] Login page
- [ ] Register page
- [ ] Dashboard page with summary cards and sparklines
- [ ] Analytics page with Recharts bar chart
- [ ] Deposits list + new + edit pages
- [ ] Subscriptions list + new + edit pages
- [ ] Import / Export page
- [ ] Settings page
- [ ] CI: GitHub Actions → Vercel deploy on push to `main`
- [ ] CI step: regenerate `src/api/types.ts` from live OpenAPI spec
