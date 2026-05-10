"""Integration tests for POST /auth/register|login|refresh."""
import pytest
from httpx import AsyncClient


# ── Register ──────────────────────────────────────────────────────────────────

async def test_register_returns_token_pair(client: AsyncClient):
    resp = await client.post("/auth/register", json={"email": "reg@test.com", "password": "pw"})
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_register_duplicate_email_is_409(client: AsyncClient):
    body = {"email": "dup@test.com", "password": "pw"}
    await client.post("/auth/register", json=body)
    resp = await client.post("/auth/register", json=body)
    assert resp.status_code == 409


async def test_register_missing_email_is_422(client: AsyncClient):
    resp = await client.post("/auth/register", json={"password": "pw"})
    assert resp.status_code == 422


async def test_register_missing_password_is_422(client: AsyncClient):
    resp = await client.post("/auth/register", json={"email": "nopw@test.com"})
    assert resp.status_code == 422


async def test_register_invalid_email_format_is_422(client: AsyncClient):
    resp = await client.post("/auth/register", json={"email": "not-an-email", "password": "pw"})
    assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

async def test_login_success(client: AsyncClient):
    await client.post("/auth/register", json={"email": "login@test.com", "password": "secret"})
    resp = await client.post("/auth/login", json={"email": "login@test.com", "password": "secret"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_login_wrong_password_is_401(client: AsyncClient):
    await client.post("/auth/register", json={"email": "wrongpw@test.com", "password": "correct"})
    resp = await client.post("/auth/login", json={"email": "wrongpw@test.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_login_unknown_email_is_401(client: AsyncClient):
    resp = await client.post("/auth/login", json={"email": "nobody@test.com", "password": "pw"})
    assert resp.status_code == 401


async def test_login_access_token_authorises_protected_endpoint(client: AsyncClient):
    await client.post("/auth/register", json={"email": "logincheck@test.com", "password": "pw"})
    login_resp = await client.post("/auth/login", json={"email": "logincheck@test.com", "password": "pw"})
    token = login_resp.json()["access_token"]
    resp = await client.get("/deposits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


# ── Refresh ───────────────────────────────────────────────────────────────────

async def test_refresh_returns_new_token_pair(client: AsyncClient):
    reg = await client.post("/auth/register", json={"email": "refresh@test.com", "password": "pw"})
    refresh_token = reg.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_refresh_new_access_token_works(client: AsyncClient):
    reg = await client.post("/auth/register", json={"email": "refreshuse@test.com", "password": "pw"})
    refresh_token = reg.json()["refresh_token"]
    new_tokens = (await client.post("/auth/refresh", json={"refresh_token": refresh_token})).json()
    resp = await client.get("/deposits", headers={"Authorization": f"Bearer {new_tokens['access_token']}"})
    assert resp.status_code == 200


async def test_refresh_with_garbage_token_is_401(client: AsyncClient):
    resp = await client.post("/auth/refresh", json={"refresh_token": "totally.invalid.token"})
    assert resp.status_code == 401


async def test_refresh_with_access_token_is_401(client: AsyncClient):
    """Access tokens must be rejected when used as refresh tokens."""
    reg = await client.post("/auth/register", json={"email": "wrongtype@test.com", "password": "pw"})
    access_token = reg.json()["access_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


# ── Auth guard ────────────────────────────────────────────────────────────────

async def test_protected_endpoint_without_token_is_403(client: AsyncClient):
    resp = await client.get("/deposits")
    assert resp.status_code == 403


async def test_protected_endpoint_with_invalid_token_is_401(client: AsyncClient):
    resp = await client.get("/deposits", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
