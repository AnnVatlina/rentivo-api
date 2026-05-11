"""Integration tests for GET /settings and PUT /settings (module system)."""
import pytest
from httpx import AsyncClient


# ── Auth guard ────────────────────────────────────────────────────────────────

async def test_get_settings_requires_auth(client: AsyncClient):
    assert (await client.get("/settings")).status_code == 403


async def test_put_settings_requires_auth(client: AsyncClient):
    assert (await client.put("/settings", json={})).status_code == 403


# ── Default values ────────────────────────────────────────────────────────────

async def test_get_settings_returns_defaults(client: AsyncClient, auth: dict):
    resp = await client.get("/settings", headers=auth["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["module_deposits"] is True
    assert data["module_subscriptions"] is True
    assert data["module_property"] is False


# ── Update ────────────────────────────────────────────────────────────────────

async def test_put_settings_updates_module(client: AsyncClient, auth: dict):
    resp = await client.put("/settings", json={"module_property": True}, headers=auth["headers"])
    assert resp.status_code == 200
    assert resp.json()["module_property"] is True


async def test_put_settings_partial_update(client: AsyncClient, auth: dict):
    await client.put("/settings", json={"module_property": True}, headers=auth["headers"])
    # only module_property changed; others stay at defaults
    data = (await client.get("/settings", headers=auth["headers"])).json()
    assert data["module_deposits"] is True
    assert data["module_property"] is True


async def test_put_settings_disable_deposits(client: AsyncClient, auth: dict):
    resp = await client.put("/settings", json={"module_deposits": False}, headers=auth["headers"])
    assert resp.status_code == 200
    assert resp.json()["module_deposits"] is False


# ── Module guard — deposits ───────────────────────────────────────────────────

async def test_deposits_blocked_when_module_disabled(client: AsyncClient, auth: dict):
    await client.put("/settings", json={"module_deposits": False}, headers=auth["headers"])
    assert (await client.get("/deposits", headers=auth["headers"])).status_code == 403


async def test_deposits_403_detail(client: AsyncClient, auth: dict):
    await client.put("/settings", json={"module_deposits": False}, headers=auth["headers"])
    resp = await client.get("/deposits", headers=auth["headers"])
    assert resp.json()["detail"] == "Module 'deposits' is not enabled"


async def test_deposits_accessible_when_module_enabled(client: AsyncClient, auth: dict):
    # default is True
    assert (await client.get("/deposits", headers=auth["headers"])).status_code == 200


# ── Module guard — subscriptions ──────────────────────────────────────────────

async def test_subscriptions_blocked_when_module_disabled(client: AsyncClient, auth: dict):
    await client.put("/settings", json={"module_subscriptions": False}, headers=auth["headers"])
    assert (await client.get("/subscriptions", headers=auth["headers"])).status_code == 403


async def test_subscriptions_accessible_when_module_enabled(client: AsyncClient, auth: dict):
    assert (await client.get("/subscriptions", headers=auth["headers"])).status_code == 200


# ── User isolation ────────────────────────────────────────────────────────────

async def test_settings_scoped_to_user(client: AsyncClient, auth: dict, second_auth: dict):
    await client.put("/settings", json={"module_deposits": False}, headers=auth["headers"])
    # second user's deposits module is still enabled
    assert (await client.get("/deposits", headers=second_auth["headers"])).status_code == 200
