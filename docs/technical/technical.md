# Rentivo API — Technical Documentation

## Architecture Overview

Rentivo API is a stateless REST API built on **FastAPI** with an **async PostgreSQL** backend.

```
Client (Web / iOS)
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
│   │   ├── subscription.py
│   │   ├── settings.py       # UserSettingsOut, UserSettingsUpdate
│   │   ├── property.py
│   │   ├── property_transaction.py
│   │   └── analytics.py      # MonthlyBreakdown (nullable module fields)
│   ├── routers/
│   │   ├── auth.py           # POST /auth/register|login|refresh
│   │   ├── settings.py       # GET/PUT /settings
│   │   ├── deposits.py       # CRUD /deposits
│   │   ├── subscriptions.py  # CRUD /subscriptions
│   │   ├── properties.py     # CRUD /properties + nested transactions + analytics
│   │   ├── analytics.py      # GET /analytics
│   │   └── export_import.py  # GET /export/csv, POST /import/csv
│   ├── services/
│   │   ├── deposit.py        # income_to_date() — simple + compound
│   │   ├── subscription.py   # monthly_cost(), next_payment_date()
│   │   ├── property.py       # monthly_cashflow(), total_summary()
│   │   └── analytics.py      # build_analytics()
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
│       └── 0006_add_default_currency_to_settings.py
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
│   │   └── technical-ui.md   # web UI spec
│   └── user/
│       ├── guide_ru.md
│       └── guide_en.md
├── docker-compose.yml
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

docker compose up --build
# Migrations run automatically on startup (railway.toml startCommand)
# API → http://localhost:8000
# Docs → http://localhost:8000/docs
```

To run tests:

```bash
# Create test DB once
docker compose exec db psql -U postgres -c "CREATE DATABASE rentivo_test;"

pytest
# or with coverage
pytest --cov=app --cov-report=term-missing
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
| billing_cycle | VARCHAR(20) | NOT NULL — weekly/monthly/quarterly/yearly/one_time |
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
| category | VARCHAR | NOT NULL |
| title | VARCHAR | NOT NULL |
| amount | NUMERIC(18,2) | NOT NULL |
| currency | VARCHAR(3) | NOT NULL |
| billing_cycle | VARCHAR(20) | NOT NULL — one_time/monthly/weekly/quarterly/yearly |
| transaction_date | DATE | nullable — for one_time only |
| start_date | DATE | nullable — for recurring |
| end_date | DATE | nullable — for recurring |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

> **Note:** The date field is named `transaction_date` (not `date`) to avoid Python namespace conflict with `datetime.date` in Pydantic v2 class bodies.

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
| `one_time` | `0` |

`next_payment_date`: advances `start_date` by billing delta until it reaches or passes today. Returns `None` if inactive, past `end_date`, or a past one_time.

### Property Cashflow

`monthly_cashflow(transactions, year, month, currency)`:
- `one_time` transactions: counted in the month their `transaction_date` falls.
- Recurring transactions: counted in months between `start_date` and `end_date`.

`total_summary(property, transactions)`:
- `total_invested` = `purchase_price` + all one_time expense amounts.
- `profit` = `sale_price − total_invested + total_income` (only if status = sold).

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

```json
// GET /settings response
{
  "id": "...",
  "user_id": "...",
  "module_deposits": true,
  "module_subscriptions": true,
  "module_property": false,
  "default_currency": "USD",
  "created_at": "..."
}

// PUT /settings request (all fields optional)
{
  "module_property": true,
  "default_currency": "RUB"
}
```

### Deposits

| Method | Path | Description |
|---|---|---|
| GET | /deposits | List all deposits (with income_to_date) |
| POST | /deposits | Create deposit |
| GET | /deposits/{id} | Get single deposit |
| PUT | /deposits/{id} | Partial update |
| DELETE | /deposits/{id} | Delete (204) |

```json
// POST /deposits — simple interest
{
  "title": "Sberbank 2026",
  "amount": "100000.00",
  "currency": "RUB",
  "open_date": "2026-01-01",
  "annual_rate": "17.0",
  "interest_type": "simple"
}

// POST /deposits — compound interest
{
  "title": "Alpha Bank",
  "amount": "100000.00",
  "currency": "RUB",
  "open_date": "2026-01-01",
  "annual_rate": "15.0",
  "interest_type": "compound",
  "compound_frequency": "monthly"
}
```

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

```json
// POST /properties
{
  "name": "Flat Moscow",
  "purchase_date": "2020-01-01",
  "purchase_price": "5000000.00",
  "currency": "RUB",
  "status": "active"
}

// POST /properties/{id}/transactions — one_time
{
  "type": "expense",
  "category": "renovation",
  "title": "Kitchen repair",
  "amount": "200000.00",
  "currency": "RUB",
  "billing_cycle": "one_time",
  "transaction_date": "2021-06-15"
}

// POST /properties/{id}/transactions — recurring
{
  "type": "income",
  "category": "rent",
  "title": "Monthly rent",
  "amount": "50000.00",
  "currency": "RUB",
  "billing_cycle": "monthly",
  "start_date": "2022-01-01"
}
```

### Analytics

#### GET /analytics?year=YYYY&currency=XXX

Returns 12 months. Module-disabled fields are `null`, not `0`.

```json
{
  "year": 2026,
  "currency": "RUB",
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

`property_income` and `property_expenses` are `null` when `module_property = false`.

### Export / Import

#### GET /export/csv

Downloads a ZIP with four CSVs:
- `deposits.csv` — columns: `id, title, bank_name, amount, currency, open_date, close_date, annual_rate, created_at`
- `subscriptions.csv` — columns: `id, title, category, amount, currency, billing_cycle, start_date, end_date, is_active, created_at`
- `properties.csv` — columns: `id, name, address, purchase_date, purchase_price, currency, status, sale_date, sale_price, sale_notes, created_at`
- `property_transactions.csv` — columns: `id, property_id, type, category, title, amount, currency, billing_cycle, transaction_date, start_date, end_date, created_at`

#### POST /import/csv

Accepts `.zip` (all four CSVs) or a single `.csv`. Deduplication by `id` + `source_id` — safe to re-import. Cross-user import generates new UUIDs.

```json
// Response 200
{"deposits": 3, "subscriptions": 2, "properties": 1, "property_transactions": 5, "skipped": 0}
```

---

## Alembic Migrations

Migrations run automatically at startup (`railway.toml` startCommand). To run manually:

```bash
alembic upgrade head
alembic revision --autogenerate -m "describe change"
alembic downgrade -1
```

Current migrations:
- `0001` — users, deposits, subscriptions
- `0002` — compound interest fields on deposits
- `0003` — user_settings table
- `0004` — properties and property_transactions tables
- `0005` — source_id on properties
- `0006` — default_currency on user_settings

---

## Testing

```bash
pytest
pytest --cov=app --cov-report=term-missing
```

216 tests. All use real PostgreSQL (`rentivo_test`). Isolation via `TRUNCATE TABLE users RESTART IDENTITY CASCADE` before each test + per-request session factory.

| File | Coverage |
|---|---|
| `test_auth.py` | Register, login, refresh |
| `test_deposits.py` | CRUD, ownership isolation, compound interest |
| `test_subscriptions.py` | CRUD, filters |
| `test_settings.py` | Module toggles, default_currency |
| `test_properties.py` | CRUD, transactions, analytics, module gate |
| `test_analytics.py` | Module-aware nulls, currency filter |
| `test_export_import.py` | ZIP export/import, cross-user import, deduplication |
| `test_services.py` | Pure unit tests: income formulas, monthly cost, cashflow |

---

## Deployment to Railway

### Minimal required variables (rentivo-api service)

```
DATABASE_URL = ${{Postgres.DATABASE_URL}}
SECRET_KEY   = <openssl rand -hex 32>
```

All other variables have code defaults (ALGORITHM=HS256, etc.).

### How it works

1. Push to `main` → GitHub Actions runs tests.
2. Tests pass → Railway auto-deploys (Wait for CI enabled).
3. At startup: `alembic upgrade head && uvicorn ...` (see `railway.toml`).

`DATABASE_URL` from Railway Postgres uses `postgresql://` scheme. `app/config.py` normalizes it to `postgresql+asyncpg://` automatically.

### CORS

`app/main.py` includes `CORSMiddleware` with `allow_origins=["*"]`. Required for the GitHub Pages web UI to call the API. Safe since all endpoints are JWT-protected.

---

## Known Limitations

- No token revocation — refresh tokens cannot be invalidated.
- Single currency per analytics query — no FX rate conversion.
- No pagination — list endpoints return all records.
- No rate limiting.
- No email verification.

---

## Roadmap

### Web UI

See [technical-ui.md](technical-ui.md).

### Backend

- [ ] Pagination on list endpoints
- [ ] Multi-currency analytics with FX rates
- [ ] Refresh token revocation
- [ ] Rate limiting
- [ ] Email verification
