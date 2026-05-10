"""Integration tests for /subscriptions CRUD endpoints."""
from decimal import Decimal

import pytest
from httpx import AsyncClient

# ── Payloads ──────────────────────────────────────────────────────────────────

MONTHLY = {
    "title": "Netflix",
    "category": "Entertainment",
    "amount": "15.99",
    "currency": "USD",
    "billing_cycle": "monthly",
    "start_date": "2026-01-01",
    "is_active": True,
}

_CYCLES = {
    "weekly":    {"amount": "10.00", "expected_monthly": Decimal("10") * 52 / 12},
    "monthly":   {"amount": "10.00", "expected_monthly": Decimal("10")},
    "quarterly": {"amount": "30.00", "expected_monthly": Decimal("10")},
    "yearly":    {"amount": "120.00", "expected_monthly": Decimal("10")},
    "one_time":  {"amount": "99.00", "expected_monthly": Decimal("0")},
}


async def _create(client: AsyncClient, headers: dict, payload: dict = MONTHLY) -> dict:
    resp = await client.post("/subscriptions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Auth guard ────────────────────────────────────────────────────────────────

async def test_list_requires_auth(client: AsyncClient):
    assert (await client.get("/subscriptions")).status_code == 403


async def test_create_requires_auth(client: AsyncClient):
    assert (await client.post("/subscriptions", json=MONTHLY)).status_code == 403


async def test_get_requires_auth(client: AsyncClient, auth: dict):
    sub = await _create(client, auth["headers"])
    assert (await client.get(f"/subscriptions/{sub['id']}")).status_code == 403


async def test_update_requires_auth(client: AsyncClient, auth: dict):
    sub = await _create(client, auth["headers"])
    assert (await client.put(f"/subscriptions/{sub['id']}", json={"title": "x"})).status_code == 403


async def test_delete_requires_auth(client: AsyncClient, auth: dict):
    sub = await _create(client, auth["headers"])
    assert (await client.delete(f"/subscriptions/{sub['id']}")).status_code == 403


# ── Create ────────────────────────────────────────────────────────────────────

async def test_create_monthly_returns_201(client: AsyncClient, auth: dict):
    resp = await client.post("/subscriptions", json=MONTHLY, headers=auth["headers"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Netflix"
    assert data["billing_cycle"] == "monthly"
    assert "next_payment_date" in data
    assert "monthly_cost" in data


async def test_create_without_optional_fields(client: AsyncClient, auth: dict):
    payload = {
        "title": "Bare minimum",
        "amount": "5.00",
        "currency": "EUR",
        "billing_cycle": "monthly",
        "start_date": "2026-01-01",
    }
    resp = await client.post("/subscriptions", json=payload, headers=auth["headers"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["category"] is None
    assert data["end_date"] is None
    assert data["is_active"] is True


async def test_create_all_billing_cycles(client: AsyncClient, auth: dict):
    for cycle in ("weekly", "monthly", "quarterly", "yearly", "one_time"):
        payload = {**MONTHLY, "billing_cycle": cycle}
        resp = await client.post("/subscriptions", json=payload, headers=auth["headers"])
        assert resp.status_code == 201, f"failed for billing_cycle={cycle}"
        assert resp.json()["billing_cycle"] == cycle


async def test_monthly_cost_normalization(client: AsyncClient, auth: dict):
    for cycle, info in _CYCLES.items():
        payload = {**MONTHLY, "billing_cycle": cycle, "amount": info["amount"]}
        data = (await client.post("/subscriptions", json=payload, headers=auth["headers"])).json()
        actual = Decimal(data["monthly_cost"])
        assert abs(actual - info["expected_monthly"]) < Decimal("0.01"), (
            f"cycle={cycle}: expected {info['expected_monthly']}, got {actual}"
        )


async def test_create_with_end_date(client: AsyncClient, auth: dict):
    payload = {**MONTHLY, "end_date": "2026-12-31"}
    data = await _create(client, auth["headers"], payload)
    assert data["end_date"] == "2026-12-31"


async def test_create_inactive(client: AsyncClient, auth: dict):
    payload = {**MONTHLY, "is_active": False}
    data = await _create(client, auth["headers"], payload)
    assert data["is_active"] is False
    assert data["next_payment_date"] is None


async def test_create_invalid_currency_is_422(client: AsyncClient, auth: dict):
    payload = {**MONTHLY, "currency": "JPY"}
    assert (await client.post("/subscriptions", json=payload, headers=auth["headers"])).status_code == 422


async def test_create_invalid_billing_cycle_is_422(client: AsyncClient, auth: dict):
    payload = {**MONTHLY, "billing_cycle": "biweekly"}
    assert (await client.post("/subscriptions", json=payload, headers=auth["headers"])).status_code == 422


async def test_create_negative_amount_is_422(client: AsyncClient, auth: dict):
    payload = {**MONTHLY, "amount": "-5.00"}
    assert (await client.post("/subscriptions", json=payload, headers=auth["headers"])).status_code == 422


async def test_create_missing_title_is_422(client: AsyncClient, auth: dict):
    payload = {k: v for k, v in MONTHLY.items() if k != "title"}
    assert (await client.post("/subscriptions", json=payload, headers=auth["headers"])).status_code == 422


# ── next_payment_date ─────────────────────────────────────────────────────────

async def test_next_payment_date_monthly_advances_correctly(client: AsyncClient, auth: dict):
    """start=2026-01-15, today > 2026-01-15 → next must be ≥ today."""
    import datetime
    payload = {**MONTHLY, "start_date": "2026-01-15"}
    data = await _create(client, auth["headers"], payload)
    if data["next_payment_date"] is not None:
        nxt = datetime.date.fromisoformat(data["next_payment_date"])
        assert nxt >= datetime.date.today()


async def test_next_payment_date_inactive_is_null(client: AsyncClient, auth: dict):
    data = await _create(client, auth["headers"], {**MONTHLY, "is_active": False})
    assert data["next_payment_date"] is None


async def test_next_payment_date_one_time_past_is_null(client: AsyncClient, auth: dict):
    payload = {**MONTHLY, "billing_cycle": "one_time", "start_date": "2020-01-01"}
    data = await _create(client, auth["headers"], payload)
    assert data["next_payment_date"] is None


async def test_next_payment_date_one_time_future_is_start_date(client: AsyncClient, auth: dict):
    payload = {**MONTHLY, "billing_cycle": "one_time", "start_date": "2099-01-01"}
    data = await _create(client, auth["headers"], payload)
    assert data["next_payment_date"] == "2099-01-01"


# ── List ──────────────────────────────────────────────────────────────────────

async def test_list_empty_for_new_user(client: AsyncClient, auth: dict):
    assert (await client.get("/subscriptions", headers=auth["headers"])).json() == []


async def test_list_returns_all_own_subscriptions(client: AsyncClient, auth: dict):
    await _create(client, auth["headers"])
    await _create(client, auth["headers"], {**MONTHLY, "title": "Spotify"})
    items = (await client.get("/subscriptions", headers=auth["headers"])).json()
    assert len(items) == 2


async def test_list_scoped_to_user(client: AsyncClient, auth: dict, second_auth: dict):
    await _create(client, auth["headers"])
    assert (await client.get("/subscriptions", headers=second_auth["headers"])).json() == []


async def test_filter_active_excludes_cancelled_and_one_time(client: AsyncClient, auth: dict):
    await _create(client, auth["headers"])                                         # active monthly
    await _create(client, auth["headers"], {**MONTHLY, "is_active": False})        # cancelled
    await _create(client, auth["headers"], {**MONTHLY, "billing_cycle": "one_time"})  # one_time
    items = (await client.get("/subscriptions?filter=active", headers=auth["headers"])).json()
    assert len(items) == 1
    assert items[0]["is_active"] is True
    assert items[0]["billing_cycle"] != "one_time"


async def test_filter_cancelled_returns_only_inactive(client: AsyncClient, auth: dict):
    await _create(client, auth["headers"])                                         # active
    await _create(client, auth["headers"], {**MONTHLY, "is_active": False})        # cancelled
    items = (await client.get("/subscriptions?filter=cancelled", headers=auth["headers"])).json()
    assert len(items) == 1
    assert items[0]["is_active"] is False


async def test_filter_one_time_returns_only_one_time(client: AsyncClient, auth: dict):
    await _create(client, auth["headers"])                                         # monthly
    await _create(client, auth["headers"], {**MONTHLY, "billing_cycle": "one_time"})
    items = (await client.get("/subscriptions?filter=one_time", headers=auth["headers"])).json()
    assert len(items) == 1
    assert items[0]["billing_cycle"] == "one_time"


async def test_invalid_filter_value_is_422(client: AsyncClient, auth: dict):
    assert (await client.get("/subscriptions?filter=unknown", headers=auth["headers"])).status_code == 422


# ── Get ───────────────────────────────────────────────────────────────────────

async def test_get_returns_subscription(client: AsyncClient, auth: dict):
    sub = await _create(client, auth["headers"])
    resp = await client.get(f"/subscriptions/{sub['id']}", headers=auth["headers"])
    assert resp.status_code == 200
    assert resp.json()["id"] == sub["id"]


async def test_get_nonexistent_is_404(client: AsyncClient, auth: dict):
    fake = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/subscriptions/{fake}", headers=auth["headers"])).status_code == 404


async def test_get_other_users_subscription_is_404(client: AsyncClient, auth: dict, second_auth: dict):
    sub = await _create(client, auth["headers"])
    assert (await client.get(f"/subscriptions/{sub['id']}", headers=second_auth["headers"])).status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

async def test_update_title(client: AsyncClient, auth: dict):
    sub = await _create(client, auth["headers"])
    resp = await client.put(f"/subscriptions/{sub['id']}", json={"title": "Updated"}, headers=auth["headers"])
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated"


async def test_cancel_subscription_nullifies_next_payment_date(client: AsyncClient, auth: dict):
    sub = await _create(client, auth["headers"])
    resp = await client.put(f"/subscriptions/{sub['id']}", json={"is_active": False}, headers=auth["headers"])
    assert resp.json()["is_active"] is False
    assert resp.json()["next_payment_date"] is None


async def test_update_nonexistent_is_404(client: AsyncClient, auth: dict):
    fake = "00000000-0000-0000-0000-000000000000"
    assert (await client.put(f"/subscriptions/{fake}", json={"title": "x"}, headers=auth["headers"])).status_code == 404


async def test_update_other_users_subscription_is_404(client: AsyncClient, auth: dict, second_auth: dict):
    sub = await _create(client, auth["headers"])
    assert (
        await client.put(f"/subscriptions/{sub['id']}", json={"title": "hack"}, headers=second_auth["headers"])
    ).status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

async def test_delete_returns_204(client: AsyncClient, auth: dict):
    sub = await _create(client, auth["headers"])
    assert (await client.delete(f"/subscriptions/{sub['id']}", headers=auth["headers"])).status_code == 204


async def test_delete_makes_subscription_unavailable(client: AsyncClient, auth: dict):
    sub = await _create(client, auth["headers"])
    await client.delete(f"/subscriptions/{sub['id']}", headers=auth["headers"])
    assert (await client.get(f"/subscriptions/{sub['id']}", headers=auth["headers"])).status_code == 404


async def test_delete_removes_from_list(client: AsyncClient, auth: dict):
    sub = await _create(client, auth["headers"])
    await client.delete(f"/subscriptions/{sub['id']}", headers=auth["headers"])
    items = (await client.get("/subscriptions", headers=auth["headers"])).json()
    assert all(s["id"] != sub["id"] for s in items)


async def test_delete_nonexistent_is_404(client: AsyncClient, auth: dict):
    fake = "00000000-0000-0000-0000-000000000000"
    assert (await client.delete(f"/subscriptions/{fake}", headers=auth["headers"])).status_code == 404


async def test_delete_other_users_subscription_is_404(client: AsyncClient, auth: dict, second_auth: dict):
    sub = await _create(client, auth["headers"])
    assert (await client.delete(f"/subscriptions/{sub['id']}", headers=second_auth["headers"])).status_code == 404
