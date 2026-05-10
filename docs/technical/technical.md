# Rentivo API — Technical Documentation

## Architecture Overview

Rentivo API is a stateless REST API built on **FastAPI** with an **async PostgreSQL** backend.

```
Client (iOS / Web)
      │
      ▼
FastAPI (uvicorn)        ← Railway service, horizontal-scalable
      │
      ▼
PostgreSQL               ← Railway managed database
```

- All database I/O is non-blocking (SQLAlchemy 2.0 async + asyncpg driver).
- Authentication is stateless JWT — no session storage required.
- Business logic (income calculation, next payment date) lives in pure Python service functions — easily testable without a database.

---

## Project Structure

```
rentivo-api/
├── app/
│   ├── main.py               # FastAPI app factory, router mounts
│   ├── config.py             # Pydantic-Settings, reads env vars
│   ├── database.py           # Async engine, session factory, Base
│   ├── models/
│   │   ├── user.py           # User SQLAlchemy model
│   │   ├── deposit.py        # Deposit SQLAlchemy model
│   │   └── subscription.py   # Subscription SQLAlchemy model
│   ├── schemas/
│   │   ├── user.py           # UserCreate, UserOut, TokenPair
│   │   ├── deposit.py        # DepositCreate/Update/Out, Currency enum
│   │   ├── subscription.py   # SubscriptionCreate/Update/Out, BillingCycle
│   │   └── analytics.py      # MonthlyBreakdown, AnalyticsResponse
│   ├── routers/
│   │   ├── auth.py           # POST /auth/register|login|refresh
│   │   ├── deposits.py       # CRUD /deposits
│   │   ├── subscriptions.py  # CRUD /subscriptions
│   │   ├── analytics.py      # GET /analytics
│   │   └── export_import.py  # GET /export/csv, POST /import/csv
│   ├── services/
│   │   ├── deposit.py        # income_to_date(), days_elapsed()
│   │   ├── subscription.py   # monthly_cost(), next_payment_date()
│   │   └── analytics.py      # build_analytics()
│   └── auth/
│       ├── jwt.py            # Token creation/validation, password hashing
│       └── dependencies.py   # get_current_user FastAPI dependency
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── tests/
│   ├── conftest.py           # DB fixtures, test client
│   ├── test_auth.py
│   ├── test_deposits.py
│   ├── test_subscriptions.py
│   ├── test_analytics.py
│   ├── test_export_import.py
│   └── test_services.py      # Pure unit tests (no DB)
├── docs/
│   ├── technical/technical.md
│   └── user/
│       ├── guide_ru.md
│       └── guide_en.md
├── docker-compose.yml        # Local dev: postgres + api
├── Dockerfile
├── railway.toml
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## Local Development Setup

### Prerequisites
- Docker + Docker Compose v2

### Steps

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd rentivo-api

# 2. Copy env file
cp .env.example .env
# Edit .env if needed (defaults work for docker-compose)

# 3. Start services
docker compose up --build

# 4. Apply migrations (first time and after model changes)
docker compose exec api alembic upgrade head

# API is now available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

To run tests locally with Docker postgres running:

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rentivo
alembic upgrade head
pytest
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | — | SQLAlchemy async DSN, e.g. `postgresql+asyncpg://user:pass@host:5432/db` |
| `SECRET_KEY` | yes | — | Long random string used to sign JWTs. Generate with `openssl rand -hex 32` |
| `ALGORITHM` | no | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | Access token lifetime in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | no | `30` | Refresh token lifetime in days |
| `APP_ENV` | no | `development` | `development` or `production` |

On Railway, set these in **Project → Variables**. `DATABASE_URL` is auto-provided by the Railway PostgreSQL plugin as `DATABASE_URL`.

---

## Database Schema

### users
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| email | VARCHAR | UNIQUE, NOT NULL, INDEX |
| hashed_password | VARCHAR | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

### deposits
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id CASCADE DELETE, INDEX |
| title | VARCHAR | NOT NULL |
| bank_name | VARCHAR | nullable |
| amount | NUMERIC(18,2) | NOT NULL |
| currency | VARCHAR(3) | NOT NULL — USD/EUR/RUB/GEL/BYN |
| open_date | DATE | NOT NULL |
| close_date | DATE | nullable (open-ended deposit) |
| annual_rate | NUMERIC(6,4) | NOT NULL — percentage, e.g. 17.0000 |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

### subscriptions
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id CASCADE DELETE, INDEX |
| title | VARCHAR | NOT NULL |
| category | VARCHAR | nullable |
| amount | NUMERIC(18,2) | NOT NULL |
| currency | VARCHAR(3) | NOT NULL |
| billing_cycle | VARCHAR(20) | NOT NULL — weekly/monthly/quarterly/yearly/one_time |
| start_date | DATE | NOT NULL |
| end_date | DATE | nullable |
| is_active | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

---

## Authentication Flow

1. **Register** — `POST /auth/register` with `{email, password}`.
   - Password is bcrypt-hashed and stored.
   - Returns `{access_token, refresh_token}`.

2. **Login** — `POST /auth/login` with same body.
   - Verifies bcrypt hash.
   - Returns new token pair.

3. **Protected endpoints** — pass `Authorization: Bearer <access_token>` header.
   - FastAPI dependency `get_current_user` validates the token, extracts `sub` (user UUID), loads the user from DB.

4. **Refresh** — `POST /auth/refresh` with `{refresh_token}`.
   - Validates the refresh token type claim.
   - Returns a new token pair. (Rotation — both tokens are replaced.)

Access tokens expire in 30 minutes. Refresh tokens expire in 30 days. Neither is stored server-side; revocation is not currently supported.

---

## Business Logic

### Deposit Income (Simple Interest)

```python
income = amount × (annual_rate / 100) × (days / 365)
```

where `days = min(today, close_date) - open_date`.

- If `close_date` is `None` (open-ended), `today` is used.
- Result is truncated to 2 decimal places at the schema layer.

### Subscription Monthly Cost Normalization

| Billing cycle | Formula |
|---|---|
| `weekly` | `amount × 52 / 12` |
| `monthly` | `amount` |
| `quarterly` | `amount / 3` |
| `yearly` | `amount / 12` |
| `one_time` | `0` |

### Subscription `next_payment_date`

A calculated field — not stored in the DB.

- Returns `None` if `is_active=False` or `end_date` is in the past.
- For `one_time`: returns `start_date` if it's in the future, else `None`.
- For recurring: advances `start_date` by the billing delta until it reaches or passes today.

---

## API Endpoints

### Auth

#### POST /auth/register
```json
// Request
{"email": "alice@example.com", "password": "secret123"}

// Response 201
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

#### POST /auth/login
Same request/response shape as `/auth/register`. Returns `200`.

#### POST /auth/refresh
```json
// Request
{"refresh_token": "eyJ..."}

// Response 200
{"access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer"}
```

---

### Deposits

All require `Authorization: Bearer <token>`.

#### GET /deposits
```json
// Response 200
[
  {
    "id": "3fa85f64-...",
    "user_id": "...",
    "title": "Sberbank 2026",
    "bank_name": "Sberbank",
    "amount": "100000.00",
    "currency": "RUB",
    "open_date": "2026-01-01",
    "close_date": "2026-12-31",
    "annual_rate": "17.0000",
    "created_at": "2026-01-01T10:00:00Z",
    "income_to_date": "2301.37",
    "days_elapsed": 49
  }
]
```

#### POST /deposits
```json
// Request
{
  "title": "Sberbank 2026",
  "bank_name": "Sberbank",
  "amount": "100000.00",
  "currency": "RUB",
  "open_date": "2026-01-01",
  "close_date": "2026-12-31",
  "annual_rate": "17.0"
}
// Response 201 — same as GET item
```

#### GET /deposits/{id}
Returns a single deposit or `404`.

#### PUT /deposits/{id}
Partial update — all fields optional. Returns updated deposit.

#### DELETE /deposits/{id}
Returns `204 No Content`.

---

### Subscriptions

All require `Authorization: Bearer <token>`.

#### GET /subscriptions
Optional query: `?filter=active|cancelled|one_time`

```json
// Response 200
[
  {
    "id": "...",
    "user_id": "...",
    "title": "Netflix",
    "category": "Entertainment",
    "amount": "15.99",
    "currency": "USD",
    "billing_cycle": "monthly",
    "start_date": "2026-01-01",
    "end_date": null,
    "is_active": true,
    "created_at": "2026-01-01T10:00:00Z",
    "next_payment_date": "2026-06-01",
    "monthly_cost": "15.99"
  }
]
```

#### POST /subscriptions
```json
{
  "title": "Netflix",
  "category": "Entertainment",
  "amount": "15.99",
  "currency": "USD",
  "billing_cycle": "monthly",
  "start_date": "2026-01-01",
  "is_active": true
}
// Response 201
```

#### GET, PUT, DELETE /subscriptions/{id} — same patterns as deposits.

---

### Analytics

#### GET /analytics?year=2026&currency=RUB

Returns monthly breakdown for all 12 months. Months before today are **actual**, months from today onward are **projected**.

```json
{
  "year": 2026,
  "currency": "RUB",
  "months": [
    {
      "month": 1,
      "year": 2026,
      "deposit_income": "2301.37",
      "subscription_expenses": "0.00",
      "net": "2301.37",
      "is_projected": false
    },
    ...
  ]
}
```

Deposit income is calculated per-month using incremental simple interest (income earned between month start and month end). Subscription expenses use the monthly normalized cost for any active subscription that overlaps the month.

---

### Export / Import

#### GET /export/csv
Downloads a ZIP file containing `deposits.csv` and `subscriptions.csv`.

**deposits.csv columns:**
`id, title, bank_name, amount, currency, open_date, close_date, annual_rate, created_at`

**subscriptions.csv columns:**
`id, title, category, amount, currency, billing_cycle, start_date, end_date, is_active, created_at`

- Dates in ISO 8601 format: `YYYY-MM-DD`
- Empty optional fields are empty strings
- `amount` / `annual_rate` as decimal strings

#### POST /import/csv
Accepts multipart form with `file` field — either a `.zip` containing one or both CSVs, or a single `.csv`.

Deduplication is by `id` — rows with an `id` that already exists for this user are skipped.

```json
// Response 200
{"deposits": 3, "subscriptions": 2, "skipped": 1}
```

---

## Alembic Migrations

### Apply all migrations
```bash
alembic upgrade head
```

### Create a new migration after changing a model
```bash
alembic revision --autogenerate -m "add column X"
# Review the generated file in alembic/versions/
alembic upgrade head
```

### Roll back one step
```bash
alembic downgrade -1
```

---

## Testing

### Run all tests
```bash
pytest
```

### With coverage report
```bash
pytest --cov=app --cov-report=term-missing
```

### What is covered

| File | Coverage focus |
|---|---|
| `test_auth.py` | Register, login, refresh — success + error paths |
| `test_deposits.py` | Full CRUD, ownership isolation |
| `test_subscriptions.py` | Full CRUD, filter query param |
| `test_analytics.py` | Empty result, result with deposit |
| `test_export_import.py` | ZIP export, import deduplication |
| `test_services.py` | Pure unit tests for income formula, monthly cost, next_payment_date |

Tests use a real PostgreSQL database (`rentivo_test`). Each test function gets a fresh transaction that is rolled back after the test, keeping tests isolated without truncating tables.

---

## Deployment to Railway

### First deploy

1. Push code to GitHub.
2. Create a Railway project → **New Service → GitHub Repo**.
3. Add a **PostgreSQL** plugin to the project. Railway injects `DATABASE_URL` automatically — but note it uses `postgresql://` not `postgresql+asyncpg://`. Fix this by adding a custom variable:
   ```
   DATABASE_URL=postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
   ```
4. Set remaining variables in **Project → Variables**:
   - `SECRET_KEY` — generate with `openssl rand -hex 32`
5. Railway will build the Dockerfile and start `uvicorn` per `railway.toml`.
6. Run migrations via Railway shell or a one-off command:
   ```bash
   railway run alembic upgrade head
   ```

### GitHub Actions CI/CD

The workflow at `.github/workflows/ci.yml`:
- Runs on every push to `main` and on PRs.
- Spins up a Postgres service container.
- Runs `alembic upgrade head` then `pytest`.
- On push to `main` (after tests pass): deploys via `railway up` **if** `RAILWAY_TOKEN` is configured. If the secret is absent the deploy step is skipped gracefully — CI still turns green.

#### Getting a Railway token

1. Open [railway.app](https://railway.app) and log in.
2. Click your avatar (top-right) → **Account Settings**.
3. Go to the **Tokens** tab → **Create Token**.
4. Give it a name (e.g. `github-actions`) and click **Create**. Copy the value — it is shown only once.

#### Adding the token to GitHub

1. Open your GitHub repository.
2. Go to **Settings → Secrets and variables → Actions**.
3. Click **New repository secret**.
4. Name: `RAILWAY_TOKEN`, Value: paste the token from above.
5. Click **Add secret**.

After saving, the next push to `main` will trigger a real deployment.

---

## Known Limitations

- **No token revocation** — refresh tokens cannot be invalidated without a token blocklist.
- **Single currency analytics** — analytics endpoint filters by a single currency; multi-currency aggregation with FX rates is not implemented.
- **No rate limiting** — all endpoints are unthrottled.
- **No pagination** — list endpoints return all records.
- **No email verification** — any email string is accepted at registration.

---

## Roadmap

### Web UI (`rentivo-ui`)

Separate GitHub repository. Deployed to **Vercel** (zero-config for Vite, per-PR preview deployments, runtime env vars via dashboard).

#### Tech stack

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

#### Environment variables

```
VITE_API_URL=https://your-api.railway.app
```

Set in Vercel dashboard per environment (preview / production). Never committed to the repository.

#### API type generation

Run once after any backend change:

```bash
npx openapi-typescript $VITE_API_URL/openapi.json -o src/api/types.ts
```

Add this as a CI step to keep types in sync automatically.

#### JWT token management

- `access_token` stored in memory (React context), not `localStorage` — XSS-safe.
- `refresh_token` stored in `localStorage`; Axios request interceptor calls `POST /auth/refresh` on 401 and retries the original request transparently.
- On logout: clear both tokens and redirect to `/login`.

#### Pages

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

#### What needs to be built

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

### iOS App (`rentivo-ios`)

Native Swift / SwiftUI application. Separate repository.
Communicates with the same REST API using `URLSession` + `Codable`.
Planned after the web UI is complete.

### Backend improvements

- [ ] Pagination (`limit` / `offset`) on list endpoints
- [ ] Multi-currency analytics with configurable FX rates
- [ ] Refresh token revocation (token blocklist in Redis or DB)
- [ ] Rate limiting (slowapi or API gateway)
- [ ] Email verification on registration
- [ ] Push notification hooks for upcoming subscription payments
