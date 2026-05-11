"""Integration tests for /deposits CRUD endpoints."""
from decimal import Decimal

import pytest
from httpx import AsyncClient

# ── Fixtures / helpers ────────────────────────────────────────────────────────

DEPOSIT_FULL = {
    "title": "Sberbank 2026",
    "bank_name": "Sberbank",
    "amount": "100000.00",
    "currency": "RUB",
    "open_date": "2026-01-01",
    "close_date": "2026-12-31",
    "annual_rate": "17.0",
}

DEPOSIT_MINIMAL = {
    "title": "Open-ended deposit",
    "amount": "50000.00",
    "currency": "USD",
    "open_date": "2020-01-01",  # past date so income_to_date > 0
    "annual_rate": "5.0",
}


async def _create(client: AsyncClient, headers: dict, payload: dict = DEPOSIT_FULL) -> dict:
    resp = await client.post("/deposits", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Auth guard ────────────────────────────────────────────────────────────────

async def test_list_requires_auth(client: AsyncClient):
    assert (await client.get("/deposits")).status_code == 403


async def test_create_requires_auth(client: AsyncClient):
    assert (await client.post("/deposits", json=DEPOSIT_FULL)).status_code == 403


async def test_get_requires_auth(client: AsyncClient, auth: dict):
    dep = await _create(client, auth["headers"])
    assert (await client.get(f"/deposits/{dep['id']}")).status_code == 403


async def test_update_requires_auth(client: AsyncClient, auth: dict):
    dep = await _create(client, auth["headers"])
    assert (await client.put(f"/deposits/{dep['id']}", json={"title": "x"})).status_code == 403


async def test_delete_requires_auth(client: AsyncClient, auth: dict):
    dep = await _create(client, auth["headers"])
    assert (await client.delete(f"/deposits/{dep['id']}")).status_code == 403


# ── Create ────────────────────────────────────────────────────────────────────

async def test_create_full_returns_201(client: AsyncClient, auth: dict):
    resp = await client.post("/deposits", json=DEPOSIT_FULL, headers=auth["headers"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Sberbank 2026"
    assert data["bank_name"] == "Sberbank"
    assert data["currency"] == "RUB"
    assert data["close_date"] == "2026-12-31"
    assert "id" in data
    assert "income_to_date" in data
    assert "days_elapsed" in data


async def test_create_minimal_no_bank_no_close_date(client: AsyncClient, auth: dict):
    resp = await client.post("/deposits", json=DEPOSIT_MINIMAL, headers=auth["headers"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["bank_name"] is None
    assert data["close_date"] is None


async def test_create_income_positive_for_past_open_date(client: AsyncClient, auth: dict):
    """Deposit opened in 2020 must already have positive accrued income."""
    data = await _create(client, auth["headers"], DEPOSIT_MINIMAL)
    assert Decimal(data["income_to_date"]) > 0
    assert data["days_elapsed"] > 0


async def test_create_income_zero_for_today_open_date(client: AsyncClient, auth: dict):
    import datetime
    payload = {**DEPOSIT_MINIMAL, "open_date": datetime.date.today().isoformat()}
    data = await _create(client, auth["headers"], payload)
    assert Decimal(data["income_to_date"]) == 0
    assert data["days_elapsed"] == 0


async def test_create_invalid_currency_is_422(client: AsyncClient, auth: dict):
    payload = {**DEPOSIT_FULL, "currency": "XYZ"}
    assert (await client.post("/deposits", json=payload, headers=auth["headers"])).status_code == 422


async def test_create_negative_amount_is_422(client: AsyncClient, auth: dict):
    payload = {**DEPOSIT_FULL, "amount": "-100"}
    assert (await client.post("/deposits", json=payload, headers=auth["headers"])).status_code == 422


async def test_create_zero_amount_is_422(client: AsyncClient, auth: dict):
    payload = {**DEPOSIT_FULL, "amount": "0"}
    assert (await client.post("/deposits", json=payload, headers=auth["headers"])).status_code == 422


async def test_create_missing_title_is_422(client: AsyncClient, auth: dict):
    payload = {k: v for k, v in DEPOSIT_FULL.items() if k != "title"}
    assert (await client.post("/deposits", json=payload, headers=auth["headers"])).status_code == 422


async def test_create_missing_amount_is_422(client: AsyncClient, auth: dict):
    payload = {k: v for k, v in DEPOSIT_FULL.items() if k != "amount"}
    assert (await client.post("/deposits", json=payload, headers=auth["headers"])).status_code == 422


async def test_create_all_currencies_accepted(client: AsyncClient, auth: dict):
    for currency in ("USD", "EUR", "RUB", "GEL", "BYN"):
        payload = {**DEPOSIT_FULL, "currency": currency}
        resp = await client.post("/deposits", json=payload, headers=auth["headers"])
        assert resp.status_code == 201, f"failed for currency {currency}"


# ── List ──────────────────────────────────────────────────────────────────────

async def test_list_empty_for_new_user(client: AsyncClient, auth: dict):
    resp = await client.get("/deposits", headers=auth["headers"])
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_returns_own_deposits(client: AsyncClient, auth: dict):
    await _create(client, auth["headers"])
    await _create(client, auth["headers"], DEPOSIT_MINIMAL)
    resp = await client.get("/deposits", headers=auth["headers"])
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_scoped_to_user(client: AsyncClient, auth: dict, second_auth: dict):
    """User A's deposits must not appear in User B's list."""
    await _create(client, auth["headers"])
    resp = await client.get("/deposits", headers=second_auth["headers"])
    assert resp.json() == []


async def test_list_includes_calculated_fields(client: AsyncClient, auth: dict):
    await _create(client, auth["headers"])
    items = (await client.get("/deposits", headers=auth["headers"])).json()
    assert all("income_to_date" in d and "days_elapsed" in d for d in items)


# ── Get ───────────────────────────────────────────────────────────────────────

async def test_get_returns_deposit(client: AsyncClient, auth: dict):
    dep = await _create(client, auth["headers"])
    resp = await client.get(f"/deposits/{dep['id']}", headers=auth["headers"])
    assert resp.status_code == 200
    assert resp.json()["id"] == dep["id"]


async def test_get_nonexistent_is_404(client: AsyncClient, auth: dict):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/deposits/{fake_id}", headers=auth["headers"])).status_code == 404


async def test_get_other_users_deposit_is_404(client: AsyncClient, auth: dict, second_auth: dict):
    dep = await _create(client, auth["headers"])
    assert (await client.get(f"/deposits/{dep['id']}", headers=second_auth["headers"])).status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

async def test_update_title(client: AsyncClient, auth: dict):
    dep = await _create(client, auth["headers"])
    resp = await client.put(f"/deposits/{dep['id']}", json={"title": "Renamed"}, headers=auth["headers"])
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed"


async def test_update_multiple_fields(client: AsyncClient, auth: dict):
    dep = await _create(client, auth["headers"])
    patch = {"title": "New name", "bank_name": "Tinkoff", "annual_rate": "20.0"}
    resp = await client.put(f"/deposits/{dep['id']}", json=patch, headers=auth["headers"])
    data = resp.json()
    assert data["title"] == "New name"
    assert data["bank_name"] == "Tinkoff"
    assert Decimal(data["annual_rate"]) == Decimal("20.0")


async def test_update_recalculates_income(client: AsyncClient, auth: dict):
    dep = await _create(client, auth["headers"], DEPOSIT_MINIMAL)
    original_income = Decimal(dep["income_to_date"])
    resp = await client.put(
        f"/deposits/{dep['id']}",
        json={"annual_rate": "10.0"},
        headers=auth["headers"],
    )
    new_income = Decimal(resp.json()["income_to_date"])
    # doubling the rate from 5% to 10% must double the income
    assert abs(new_income - original_income * 2) < Decimal("0.02")


async def test_update_nonexistent_is_404(client: AsyncClient, auth: dict):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert (
        await client.put(f"/deposits/{fake_id}", json={"title": "x"}, headers=auth["headers"])
    ).status_code == 404


async def test_update_other_users_deposit_is_404(client: AsyncClient, auth: dict, second_auth: dict):
    dep = await _create(client, auth["headers"])
    assert (
        await client.put(f"/deposits/{dep['id']}", json={"title": "hack"}, headers=second_auth["headers"])
    ).status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

async def test_delete_returns_204(client: AsyncClient, auth: dict):
    dep = await _create(client, auth["headers"])
    assert (await client.delete(f"/deposits/{dep['id']}", headers=auth["headers"])).status_code == 204


async def test_delete_makes_deposit_unavailable(client: AsyncClient, auth: dict):
    dep = await _create(client, auth["headers"])
    await client.delete(f"/deposits/{dep['id']}", headers=auth["headers"])
    assert (await client.get(f"/deposits/{dep['id']}", headers=auth["headers"])).status_code == 404


async def test_delete_removes_from_list(client: AsyncClient, auth: dict):
    dep = await _create(client, auth["headers"])
    await client.delete(f"/deposits/{dep['id']}", headers=auth["headers"])
    items = (await client.get("/deposits", headers=auth["headers"])).json()
    assert all(d["id"] != dep["id"] for d in items)


async def test_delete_nonexistent_is_404(client: AsyncClient, auth: dict):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert (await client.delete(f"/deposits/{fake_id}", headers=auth["headers"])).status_code == 404


async def test_delete_other_users_deposit_is_404(client: AsyncClient, auth: dict, second_auth: dict):
    dep = await _create(client, auth["headers"])
    assert (await client.delete(f"/deposits/{dep['id']}", headers=second_auth["headers"])).status_code == 404


# ── Compound interest ─────────────────────────────────────────────────────────

COMPOUND_PAYLOAD = {
    "title": "Compound dep",
    "amount": "100000.00",
    "currency": "RUB",
    "open_date": "2020-01-01",
    "annual_rate": "10.0",
    "interest_type": "compound",
    "compound_frequency": "monthly",
}


async def test_create_compound_deposit_returns_201(client: AsyncClient, auth: dict):
    resp = await client.post("/deposits", json=COMPOUND_PAYLOAD, headers=auth["headers"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["interest_type"] == "compound"
    assert data["compound_frequency"] == "monthly"


async def test_compound_income_greater_than_simple(client: AsyncClient, auth: dict):
    """Compound income must be strictly greater than simple for same rate and period."""
    simple = (await client.post("/deposits", json={
        **COMPOUND_PAYLOAD, "interest_type": "simple", "compound_frequency": None,
    }, headers=auth["headers"])).json()
    compound = (await client.post("/deposits", json=COMPOUND_PAYLOAD, headers=auth["headers"])).json()
    assert Decimal(compound["income_to_date"]) > Decimal(simple["income_to_date"])


async def test_compound_missing_frequency_is_422(client: AsyncClient, auth: dict):
    payload = {**COMPOUND_PAYLOAD, "compound_frequency": None}
    assert (await client.post("/deposits", json=payload, headers=auth["headers"])).status_code == 422


async def test_simple_with_frequency_is_422(client: AsyncClient, auth: dict):
    payload = {**DEPOSIT_FULL, "interest_type": "simple", "compound_frequency": "monthly"}
    assert (await client.post("/deposits", json=payload, headers=auth["headers"])).status_code == 422


async def test_invalid_interest_type_is_422(client: AsyncClient, auth: dict):
    payload = {**DEPOSIT_FULL, "interest_type": "magic"}
    assert (await client.post("/deposits", json=payload, headers=auth["headers"])).status_code == 422


async def test_invalid_compound_frequency_is_422(client: AsyncClient, auth: dict):
    payload = {**COMPOUND_PAYLOAD, "compound_frequency": "biweekly"}
    assert (await client.post("/deposits", json=payload, headers=auth["headers"])).status_code == 422


async def test_default_interest_type_is_simple(client: AsyncClient, auth: dict):
    data = await _create(client, auth["headers"], DEPOSIT_MINIMAL)
    assert data["interest_type"] == "simple"
    assert data["compound_frequency"] is None
