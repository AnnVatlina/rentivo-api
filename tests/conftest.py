import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base, get_db
from app.main import app

_base_url, _, _db_name = settings.DATABASE_URL.rpartition("/")
TEST_DATABASE_URL = f"{_base_url}/rentivo_test"

engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create tables once for the session; drop them after all tests finish."""
    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def _drop():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_drop())


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Truncates all user data before each test (cascades to deposits and
    subscriptions), then wires the app to use per-request test sessions.

    Each request gets its own session via override_get_db — this matches
    how FastAPI operates in production and avoids asyncpg task-affinity
    errors that occur when a session is shared across async tasks.
    """
    async with TestingSessionLocal() as cleanup:
        await cleanup.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await cleanup.commit()

    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Shared auth helpers ────────────────────────────────────────────────────────

async def _register(client: AsyncClient, email: str, password: str = "testpass123") -> dict:
    resp = await client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def auth(client: AsyncClient) -> dict:
    """Primary test user. Returns dict with 'headers', 'tokens', 'email', 'password'."""
    tokens = await _register(client, "primary@test.com")
    return {
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
        "tokens": tokens,
        "email": "primary@test.com",
        "password": "testpass123",
    }


@pytest_asyncio.fixture
async def second_auth(client: AsyncClient) -> dict:
    """Second test user for ownership-isolation tests."""
    tokens = await _register(client, "second@test.com")
    return {
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
        "tokens": tokens,
        "email": "second@test.com",
        "password": "testpass123",
    }
