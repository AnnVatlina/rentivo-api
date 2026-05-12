# Rentivo API — Technical Documentation

## Architecture Overview

Rentivo API is a stateless REST API built on **FastAPI** with an **async PostgreSQL** backend.

```
Browser (GitHub Pages)
      │
      ▼
FastAPI (uvicorn)        ← Railway service
      │
      ▼
PostgreSQL               ← Railway Postgres plugin
```

- All database I/O is non-blocking (SQLAlchemy 2.0 async + asyncpg driver).
- Authentication is stateless JWT — no session storage required.
- Business logic lives in pure Python service functions (no DB calls) — easily testable.

---

## Project Structure

```
rentivo-api/
├── app/
│   ├── main.py               # FastAPI app, router mounts, CORS middleware
│   ├── config.py             # Pydantic-Settings; normalizes postgresql:// → asyncpg
│   ├── database.py           # Async engine, session factory, Base
│   ├── models/
│   │   ├── user.py
│   │   ├── deposit.py        # interest_type, compound_frequency, source_id
│   │   ├── subscription.py   # source_id
│   │   ├── user_settings.py  # module flags, default_currency
│   │   ├── property.py       # source_id
│   │   └── property_transaction.py  # transaction_date (not date)
│   ├── schemas/
│   │   ├── user.py
│   │   ├── deposit.py        # InterestType, CompoundFrequency enums
│   │   ├── subscription.py   # BillingCycle: weekly/monthly/quarterly/yearly/biennial/one_time
│   │   ├── settings.py       # UserSettingsOut, UserSettingsUpdate
│   │   ├── property.py       # PropertyAnalyticsResponse with currency field
│   │   ├── property_transaction.py  # TransactionType, TransactionCategory, TransactionBillingCycle
│   │   └── analytics.py      # MonthlyBreakdown, AnalyticsResponse (deposit_currency, subscription_currency)
│   ├── routers/
│   │   ├── auth.py           # POST /auth/register|login|refresh
│   │   ├── settings.py       # GET/PUT /settings, POST /settings/demo-data, DELETE /settings/data
│   │   ├── deposits.py       # CRUD /deposits
│   │   ├── subscriptions.py  # CRUD /subscriptions
│   │   ├── properties.py     # CRUD /properties + nested transactions + analytics
│   │   ├── analytics.py      # GET /analytics
│   │   └── export_import.py  # GET /export/csv, POST /import/csv
│   ├── services/
│   │   ├── deposit.py        # income_to_date() — simple + compound
│   │   ├── subscription.py   # monthly_cost(), next_payment_date() — incl. biennial
│   │   ├── property.py       # monthly_cashflow() (currency-agnostic), total_summary()
│   │   └── analytics.py      # build_analytics() — currency-agnostic, returns native currencies
│   └── auth/
│       ├── jwt.py            # Token creation/validation, bcrypt password hashing
│       └── dependencies.py   # get_current_user, require_module() factory
├── alembic/
│   └── versions/
│       ├── 0001_initial_schema.py
│       ├── 0002_add_compound_interest.py
│       ├── 0003_add_user_settings.py
│       ├── 0004_add_properties_and_transactions.py
│       ├── 0005_add_property_source_id.py
│       ├── 0006_add_default_currency_to_settings.py
│       └── 0007_rename_transaction_date.py   # conditional — safe on fresh DBs
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_deposits.py
│   ├── test_subscriptions.py
│   ├── test_settings.py
│   ├── test_properties.py
│   ├── test_analytics.py
│   ├── test_export_import.py
│   └── test_services.py
├── docs/
│   ├── technical/
│   │   ├── technical.md      # this file
│   │   └── technical-ui.md   # web UI technical spec
│   └── user/
│       ├── guide_ru.md
│       └── guide_en.md
├── docker-compose.yml        # db + api (--reload) + ui services
├── Dockerfile
├── railway.toml
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## Local Development Setup

```bash
git clone https://github.com/AnnVatlina/rentivo-api
cd rentivo-api
cp .env.example .env

docker-compose up --build
# Migrations run automatically on startup
# API → http://localhost:8000
# Docs → http://localhost:8000/docs
# UI  → http://localhost:5173 (served from rentivo-ui volume mount)
```

To run tests:

```bash
# Create test DB once
docker-compose exec db psql -U postgres -c "CREATE DATABASE rentivo_test;"

docker-compose exec api pytest
# or with coverage
docker-compose exec api pytest --cov=app --cov-report=term-missing
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | — | `postgresql+asyncpg://...` or `postgresql://...` (auto-normalized) |
| `SECRET_KEY` | yes | — | JWT signing key. Generate: `openssl rand -hex 32` |
| `ALGORITHM` | no | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | no | `30` | Refresh token lifetime |

On Railway, set only `DATABASE_URL = ${{Postgres.DATABASE_URL}}` and `SECRET_KEY`. The code automatically replaces `postgresql://` with `postgresql+asyncpg://` at startup.

---

## Database Schema

### users
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| email | VARCHAR | UNIQUE, NOT NULL, INDEX |
| hashed_password | VARCHAR | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

### user_settings
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id CASCADE, UNIQUE, INDEX |
| module_deposits | BOOLEAN | NOT NULL, default true |
| module_subscriptions | BOOLEAN | NOT NULL, default true |
| module_property | BOOLEAN | NOT NULL, default false |
| default_currency | VARCHAR(3) | NOT NULL, default 'USD' |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

Created automatically on registration. One row per user.

### deposits
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id CASCADE, INDEX |
| title | VARCHAR | NOT NULL |
| bank_name | VARCHAR | nullable |
| amount | NUMERIC(18,2) | NOT NULL |
| currency | VARCHAR(3) | NOT NULL |
| open_date | DATE | NOT NULL |
| close_date | DATE | nullable |
| annual_rate | NUMERIC(6,4) | NOT NULL |
| interest_type | VARCHAR(20) | NOT NULL, default 'simple' |
| compound_frequency | VARCHAR(20) | nullable — daily/monthly/quarterly/annually |
| source_id | UUID | nullable, INDEX — original UUID when imported |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

### subscriptions
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id CASCADE, INDEX |
| title | VARCHAR | NOT NULL |
| category | VARCHAR | nullable |
| amount | NUMERIC(18,2) | NOT NULL |
| currency | VARCHAR(3) | NOT NULL |
| billing_cycle | VARCHAR(20) | NOT NULL — weekly/monthly/quarterly/yearly/**biennial**/one_time |
| start_date | DATE | NOT NULL |
| end_date | DATE | nullable |
| is_active | BOOLEAN | NOT NULL |
| source_id | UUID | nullable, INDEX |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

### properties
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id CASCADE, INDEX |
| name | VARCHAR | NOT NULL |
| address | VARCHAR | nullable |
| purchase_date | DATE | NOT NULL |
| purchase_price | NUMERIC(18,2) | NOT NULL |
| currency | VARCHAR(3) | NOT NULL |
| status | VARCHAR(20) | NOT NULL — active/sold |
| sale_date | DATE | nullable |
| sale_price | NUMERIC(18,2) | nullable |
| sale_notes | VARCHAR | nullable |
| source_id | UUID | nullable, INDEX |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

### property_transactions
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| property_id | UUID | FK → properties.id CASCADE, INDEX |
| type | VARCHAR(20) | NOT NULL — income/expense |
| category | VARCHAR(50) | NOT NULL — mortgage/utilities/tax/maintenance/rent/other |
| title | VARCHAR | NOT NULL |
| amount | NUMERIC(18,2) | NOT NULL |
| currency | VARCHAR(3) | NOT NULL |
| billing_cycle | VARCHAR(20) | NOT NULL — one_time/monthly/weekly/quarterly/yearly |
| transaction_date | DATE | nullable — for one_time only |
| start_date | DATE | nullable — for recurring |
| end_date | DATE | nullable — for recurring |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

> **Note:** The date field is named `transaction_date` (not `date`) to avoid Python namespace conflict with `datetime.date` in Pydantic v2 class bodies. Migration 0007 renames the column conditionally (safe on fresh databases).

---

## Authentication Flow

1. **Register** — `POST /auth/register` → bcrypt-hashed password, creates UserSettings row, returns token pair.
2. **Login** — `POST /auth/login` → verifies hash, returns new token pair.
3. **Protected endpoints** — `Authorization: Bearer <access_token>` header required.
4. **Refresh** — `POST /auth/refresh` → returns new token pair (rotation).

Access tokens expire in 30 min, refresh tokens in 30 days. Neither stored server-side.

---

## Module System

Each user has a `UserSettings` row with boolean module flags. Disabled modules:
- Return `403 Forbidden` on module-specific endpoints.
- Return `null` (not `0`) for their analytics columns.

The `require_module(name)` dependency factory in `app/auth/dependencies.py` enforces this per-router:

```python
router = APIRouter(dependencies=[Depends(get_current_user), Depends(require_module("property"))])
```

---

## Business Logic

### Deposit Income

**Simple interest:**
```
income = amount × (annual_rate / 100) × (days / 365)
days = min(today, close_date) − open_date
```

**Compound interest:**
```
A = amount × (1 + r/n)^(n×t)
income = A − amount

r = annual_rate / 100
t = days / 365
n = periods per year: daily=365, monthly=12, quarterly=4, annually=1
```

### Subscription Monthly Cost

| Billing cycle | Formula |
|---|---|
| `weekly` | `amount × 52 / 12` |
| `monthly` | `amount` |
| `quarterly` | `amount / 3` |
| `yearly` | `amount / 12` |
| `biennial` | `amount / 24` |
| `one_time` | `0` |

`next_payment_date`: advances `start_date` by billing delta until it reaches or passes today. Returns `None` if inactive, past `end_date`, or a past one_time.

### Subscription Analytics Cost

For non-monthly billing cycles (weekly, quarterly, yearly, biennial), the **full payment amount** is shown in the month when the payment actually falls — not spread across months. Monthly subscriptions show their amount every month.

### Property Cashflow

`monthly_cashflow(transactions, year, month, currency)`:
- Currency parameter is kept for signature compatibility; **all transactions are now included regardless of their currency** — conversion is done on the frontend.
- `one_time` transactions: counted in the month their `transaction_date` falls.
- Recurring transactions: counted in months between `start_date` and `end_date`.

`total_summary(property, transactions)`:
- `total_invested` = `purchase_price` + all one_time expense amounts (same currency as property).
- `profit` = `sale_price − total_invested + total_income` (only if status = sold).

### Property Analytics Currency

`GET /properties/{id}/analytics` derives the response `currency` from the **most common currency among existing transactions**, not from `prop.currency`. This handles the common case where a property is created in one currency but transactions are imported in another.

### Global Analytics Currency

`GET /analytics` no longer filters deposits and subscriptions by the requested `currency`. Instead:
- All items are summed regardless of their native currency.
- The response includes `deposit_currency` and `subscription_currency` fields (most common currency among active items).
- The frontend uses these fields with the open.er-api.com exchange rate API to convert values for display.

---

## API Endpoints

All endpoints except `/auth/*` and `/health` require `Authorization: Bearer <token>`.

### Auth

| Method | Path | Description |
|---|---|---|
| POST | /auth/register | Create account, returns token pair |
| POST | /auth/login | Login, returns token pair |
| POST | /auth/refresh | Refresh tokens |

### Settings

| Method | Path | Description |
|---|---|---|
| GET | /settings | Get user settings |
| PUT | /settings | Update settings (partial) |
| POST | /settings/demo-data | Load demo deposits, subscriptions, property |
| DELETE | /settings/data | Delete all user data (keeps settings) |

### Deposits

| Method | Path | Description |
|---|---|---|
| GET | /deposits | List all deposits (with income_to_date, days_elapsed) |
| POST | /deposits | Create deposit |
| GET | /deposits/{id} | Get single deposit |
| PUT | /deposits/{id} | Partial update |
| DELETE | /deposits/{id} | Delete (204) |

### Subscriptions

| Method | Path | Description |
|---|---|---|
| GET | /subscriptions | List all (with monthly_cost, next_payment_date) |
| POST | /subscriptions | Create |
| GET | /subscriptions/{id} | Get single |
| PUT | /subscriptions/{id} | Partial update |
| DELETE | /subscriptions/{id} | Delete (204) |

### Properties

Requires `module_property = true` in user settings (otherwise 403).

| Method | Path | Description |
|---|---|---|
| GET | /properties | List all properties |
| POST | /properties | Create property |
| GET | /properties/{id} | Get with summary (total_invested, profit) |
| PUT | /properties/{id} | Partial update |
| DELETE | /properties/{id} | Delete (204) |
| GET | /properties/{id}/transactions | List transactions |
| POST | /properties/{id}/transactions | Add transaction |
| PUT | /properties/{id}/transactions/{tx_id} | Update transaction |
| DELETE | /properties/{id}/transactions/{tx_id} | Delete (204) |
| GET | /properties/{id}/analytics?year=N | Monthly cashflow for year |

Transaction categories: `mortgage`, `utilities`, `tax`, `maintenance`, `rent`, `other`.

### Analytics

#### GET /analytics?year=YYYY&currency=XXX

Returns 12 months. Module-disabled fields are `null`, not `0`. All deposits and subscriptions are included regardless of their native currency; `deposit_currency` and `subscription_currency` tell the frontend what to convert from.

```json
{
  "year": 2026,
  "currency": "USD",
  "deposit_currency": "GEL",
  "subscription_currency": "USD",
  "months": [
    {
      "month": 1,
      "year": 2026,
      "deposit_income": "2301.37",
      "subscription_expenses": "1200.00",
      "property_income": null,
      "property_expenses": null,
      "net": "1101.37",
      "is_projected": false
    }
  ]
}
```

#### GET /properties/{id}/analytics?year=YYYY

```json
{
  "property_id": "...",
  "year": 2026,
  "currency": "GEL",
  "months": [
    {
      "month": 1,
      "income": "0.00",
      "expenses": "95.55",
      "net": "-95.55",
      "is_projected": false
    }
  ]
}
```

### Export / Import

#### GET /export/csv

Downloads a ZIP with four CSVs:
- `deposits.csv` — `id, title, bank_name, amount, currency, open_date, close_date, annual_rate, created_at`
- `subscriptions.csv` — `id, title, category, amount, currency, billing_cycle, start_date, end_date, is_active, created_at`
- `properties.csv` — `id, name, address, purchase_date, purchase_price, currency, status, sale_date, sale_price, sale_notes, created_at`
- `property_transactions.csv` — `id, property_id, type, category, title, amount, currency, billing_cycle, transaction_date, start_date, end_date, created_at`

#### POST /import/csv

Accepts `.zip` (all four CSVs) or a single `.csv`. Deduplication by `id` + `source_id` — safe to re-import. Cross-user import generates new UUIDs. Property transactions require the `property_id` to already exist for that user.

```json
// Response 200
{"deposits": 3, "subscriptions": 2, "properties": 1, "property_transactions": 81, "skipped": 0}
```

---

## Alembic Migrations

Migrations run automatically at startup. To run manually:

```bash
docker-compose exec api alembic upgrade head
docker-compose exec api alembic revision --autogenerate -m "describe change"
docker-compose exec api alembic downgrade -1
```

| Migration | Change |
|---|---|
| `0001` | users, deposits, subscriptions |
| `0002` | compound interest fields on deposits |
| `0003` | user_settings table |
| `0004` | properties and property_transactions tables |
| `0005` | source_id on properties |
| `0006` | default_currency on user_settings |
| `0007` | conditional rename of `date` → `transaction_date` on property_transactions |

Migration 0007 uses a conditional `DO $$ ... IF EXISTS ... END $$` block — safe on both fresh databases (column already named correctly) and upgraded ones.

---

## Testing

```bash
docker-compose exec api pytest
docker-compose exec api pytest --cov=app --cov-report=term-missing
```

**222 tests.** All use real PostgreSQL (`rentivo_test`). Isolation via `TRUNCATE TABLE users RESTART IDENTITY CASCADE` before each test + per-request session factory.

| File | What it covers |
|---|---|
| `test_auth.py` | Register, login, refresh, token validation |
| `test_deposits.py` | CRUD, ownership isolation, simple + compound interest |
| `test_subscriptions.py` | CRUD, billing cycles including biennial, filters |
| `test_settings.py` | Module toggles, default_currency, demo data |
| `test_properties.py` | CRUD, transactions, analytics, module gate |
| `test_analytics.py` | Module-aware nulls, multi-currency handling, native currency fields |
| `test_export_import.py` | ZIP export/import, cross-user import, deduplication |
| `test_services.py` | Pure unit tests: income formulas, monthly cost, cashflow |

---

## Deployment to Railway

### Required variables (rentivo-api service)

```
DATABASE_URL = ${{Postgres.DATABASE_URL}}
SECRET_KEY   = <openssl rand -hex 32>
```

### How it works

1. Push to `main` → GitHub Actions runs all 222 tests.
2. Tests pass → Railway auto-deploys (Wait for CI enabled).
3. At startup: `alembic upgrade head && uvicorn app.main:app ...` (see `railway.toml`).

`DATABASE_URL` from Railway Postgres uses `postgresql://` scheme. `app/config.py` normalizes it to `postgresql+asyncpg://` automatically.

### CORS

`app/main.py` includes `CORSMiddleware` with `allow_origins=["*"]`. Required for the GitHub Pages web UI to call the API. Safe since all endpoints are JWT-protected.

---

## Known Limitations

- No token revocation — refresh tokens cannot be invalidated server-side.
- No pagination on list endpoints — all records returned at once (pagination is client-side in the UI).
- No rate limiting.
- No email verification.
- Exchange rate conversion uses a third-party free API (open.er-api.com) on the frontend — no server-side FX conversion.
- Multi-currency analytics: if a user has deposits in multiple different currencies, they are summed as-is (mixed totals). The `deposit_currency` field reflects the most common currency.
