# Rentivo API — Agent Instructions

Personal finance REST API built with FastAPI + PostgreSQL. Tracks bank deposits and subscriptions, calculates interest income and subscription costs, serves a monthly analytics view.

## Quick orientation

```
app/
  main.py          — FastAPI app, router mounts
  config.py        — Settings (pydantic-settings, reads .env)
  database.py      — Async engine, session factory, Base

  models/          — SQLAlchemy 2.0 ORM (one file per table)
  schemas/         — Pydantic v2 (Create / Update / Out per resource)
  services/        — Pure Python business logic (no DB calls)
  routers/         — One file per domain, mounted in main.py
  auth/            — JWT helpers + get_current_user dependency

alembic/           — Migrations
tests/             — pytest-asyncio integration tests
```

## Environment

Copy `.env.example` to `.env`. All variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:port/db` |
| `SECRET_KEY` | Long random string for JWT signing |
| `ALGORITHM` | JWT algorithm (default `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Default `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Default `30` |

## Running locally

```bash
docker compose up --build          # starts postgres + api
docker compose exec api alembic upgrade head
# API → http://localhost:8000
# Docs → http://localhost:8000/docs
```

## Running tests

Tests require a running PostgreSQL. The test suite derives the test DB name from `DATABASE_URL` by replacing the trailing database name with `rentivo_test` — that database must exist.

```bash
# Create test DB once (with Docker postgres running):
docker compose exec db psql -U postgres -c "CREATE DATABASE rentivo_test;"

# Run tests
pytest

# With coverage
pytest --cov=app --cov-report=term-missing
```

`pytest.ini` sets `asyncio_mode = auto` — no `@pytest.mark.asyncio` needed on individual tests.

## Migrations

```bash
# Apply all
alembic upgrade head

# Create after changing a model
alembic revision --autogenerate -m "describe the change"
# Review the generated file, then:
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

`alembic/env.py` imports all models so autogenerate can detect them. When adding a new model, import it there alongside the others.

---

## Code conventions

### Models (`app/models/`)

SQLAlchemy 2.0 mapped columns with Python type annotations. UUID primary keys, `user_id` FK with `ondelete="CASCADE"`. Enums stored as `String` columns (not PG enums) — easier to migrate.

```python
class Thing(Base):
    __tablename__ = "things"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # ... columns
```

### Schemas (`app/schemas/`)

Three classes per resource: `ThingCreate`, `ThingUpdate` (all optional fields), `ThingOut` (`model_config = {"from_attributes": True}`). Calculated fields that don't exist on the model go only in `ThingOut`.

### Services (`app/services/`)

Pure functions — no DB calls, no FastAPI dependencies. Accept model instances and return values. The router calls service functions to compute calculated fields before returning.

```python
# service
def some_calc(thing: Thing) -> Decimal: ...

# router — _enrich pattern
def _enrich(thing: Thing) -> ThingOut:
    return ThingOut(**thing.__dict__, calculated_field=svc.some_calc(thing))
```

### Routers (`app/routers/`)

- `router = APIRouter(dependencies=[Depends(get_current_user)])` — protects all routes.
- Re-declare `current_user: User = Depends(get_current_user)` in each handler that needs the user object.
- All queries filter by `user_id == current_user.id` — never expose other users' data.
- Private `_get_thing()` helper raises `404` when the record doesn't exist or belongs to another user.
- Use `body.model_dump(exclude_unset=True)` for partial updates (PUT).
- `DELETE` returns `204 No Content`.

### Auth

`get_current_user` (in `app/auth/dependencies.py`) validates the Bearer token and returns a `User` ORM object. It raises `401` for invalid/expired tokens and `403` is produced by FastAPI's `HTTPBearer` when the header is absent.

### Business logic

**Deposit income** (simple interest):
```
income = amount × (annual_rate / 100) × (days / 365)
days = min(today, close_date) - open_date   # capped at close_date
```

**Subscription monthly cost**:
```
weekly   → amount × 52 / 12
monthly  → amount
quarterly→ amount / 3
yearly   → amount / 12
one_time → 0
```

`next_payment_date` advances `start_date` by the billing delta until it reaches or passes today. Returns `None` if inactive, past `end_date`, or a past one_time.

---

## Adding a new resource

1. **Model** — `app/models/thing.py` following the pattern above.
2. **Import in `alembic/env.py`** — add `import app.models.thing`.
3. **Migration** — `alembic revision --autogenerate -m "add things table"`.
4. **Schemas** — `app/schemas/thing.py` with Create / Update / Out.
5. **Service** — `app/services/thing.py` if there are calculated fields.
6. **Router** — `app/routers/thing.py`; add `router.include_router(...)` in `app/main.py`.
7. **Tests** — `tests/test_things.py`; cover auth guard, CRUD happy paths, 422 validation, 404 for missing/wrong-user, user isolation.

---

## Test conventions

Tests live in `tests/`. Each test file covers one router. The test suite uses real PostgreSQL (not mocks).

### Isolation

`conftest.py` uses two mechanisms:

1. **Table truncation**: the `client` fixture runs `TRUNCATE TABLE users RESTART IDENTITY CASCADE` before each test (cascades to deposits and subscriptions). Never add extra truncate calls — isolation is automatic.
2. **Per-request sessions**: `get_db` is overridden with a factory that creates a fresh `AsyncSession` for every HTTP request. This matches production FastAPI behaviour and avoids asyncpg connection-affinity errors that occur when a session is shared across async tasks.

Because isolation is per-test, all tests can use the same email addresses (`primary@test.com`, `second@test.com`) — no need to generate unique values.

### Fixtures

| Fixture | Type | Provides |
|---|---|---|
| `client` | `AsyncClient` | Configured httpx client wired to the test DB session |
| `auth` | `dict` | Primary user: `headers`, `tokens`, `email`, `password` |
| `second_auth` | `dict` | Second user — use for ownership isolation tests |

### Test anatomy

```python
async def test_get_other_users_thing_is_404(client: AsyncClient, auth: dict, second_auth: dict):
    thing = (await client.post("/things", json=PAYLOAD, headers=auth["headers"])).json()
    resp = await client.get(f"/things/{thing['id']}", headers=second_auth["headers"])
    assert resp.status_code == 404
```

Cover for every endpoint:
- Auth guard (no token → 403, bad token → 401)
- 422 for invalid field values
- 404 for nonexistent IDs and cross-user access
- Happy path (correct status code + response shape)
- User isolation (one user cannot see another's data)

---

## Deployment (Railway)

Set in Railway **Project → Variables**:
- `DATABASE_URL` — use asyncpg form: `postgresql+asyncpg://...`
- `SECRET_KEY` — `openssl rand -hex 32`

Railway builds from `Dockerfile`; start command is in `railway.toml`. Run migrations via:
```bash
railway run alembic upgrade head
```

CI/CD is in `.github/workflows/ci.yml` — runs tests then deploys on push to `main`. Requires `RAILWAY_TOKEN` secret in GitHub repo settings.
