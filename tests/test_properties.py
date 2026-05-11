"""Integration tests for /properties (CRUD, transactions, analytics, module guard)."""
from decimal import Decimal

import pytest
from httpx import AsyncClient

# ── Payloads ──────────────────────────────────────────────────────────────────

PROPERTY = {
    "name": "Moscow flat",
    "address": "Lenina 1",
    "purchase_date": "2020-01-01",
    "purchase_price": "5000000.00",
    "currency": "RUB",
    "status": "active",
}

TX_RENT = {
    "type": "income",
    "category": "rent",
    "title": "Monthly rent",
    "amount": "50000.00",
    "currency": "RUB",
    "billing_cycle": "monthly",
    "start_date": "2020-02-01",
}

TX_MORTGAGE = {
    "type": "expense",
    "category": "mortgage",
    "title": "Bank mortgage",
    "amount": "30000.00",
    "currency": "RUB",
    "billing_cycle": "monthly",
    "start_date": "2020-01-15",
}

TX_ONE_TIME = {
    "type": "expense",
    "category": "maintenance",
    "title": "Repair",
    "amount": "100000.00",
    "currency": "RUB",
    "billing_cycle": "one_time",
    "transaction_date": "2020-06-01",
}


async def _enable_property(client: AsyncClient, headers: dict):
    await client.put("/settings", json={"module_property": True}, headers=headers)


async def _create_property(client: AsyncClient, headers: dict, payload: dict = PROPERTY) -> dict:
    resp = await client.post("/properties", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_tx(client: AsyncClient, headers: dict, prop_id: str, payload: dict) -> dict:
    resp = await client.post(f"/properties/{prop_id}/transactions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Module guard ──────────────────────────────────────────────────────────────

async def test_properties_requires_module(client: AsyncClient, auth: dict):
    # module_property defaults to False
    assert (await client.get("/properties", headers=auth["headers"])).status_code == 403


async def test_properties_module_guard_detail(client: AsyncClient, auth: dict):
    resp = await client.get("/properties", headers=auth["headers"])
    assert resp.json()["detail"] == "Module 'property' is not enabled"


async def test_properties_accessible_when_enabled(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    assert (await client.get("/properties", headers=auth["headers"])).status_code == 200


async def test_properties_requires_auth(client: AsyncClient):
    assert (await client.get("/properties")).status_code == 403


# ── Property CRUD ─────────────────────────────────────────────────────────────

async def test_create_property_returns_201(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    resp = await client.post("/properties", json=PROPERTY, headers=auth["headers"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Moscow flat"
    assert data["status"] == "active"
    assert data["summary"] is None  # list endpoint has no summary


async def test_create_sold_property(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    payload = {**PROPERTY, "status": "sold", "sale_date": "2023-06-01", "sale_price": "7000000.00"}
    resp = await client.post("/properties", json=payload, headers=auth["headers"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "sold"
    assert data["sale_price"] == "7000000.00"


async def test_create_sold_without_sale_date_is_422(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    payload = {**PROPERTY, "status": "sold", "sale_price": "7000000.00"}
    assert (await client.post("/properties", json=payload, headers=auth["headers"])).status_code == 422


async def test_create_sold_without_sale_price_is_422(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    payload = {**PROPERTY, "status": "sold", "sale_date": "2023-06-01"}
    assert (await client.post("/properties", json=payload, headers=auth["headers"])).status_code == 422


async def test_list_properties(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    await _create_property(client, auth["headers"])
    await _create_property(client, auth["headers"], {**PROPERTY, "name": "Dacha"})
    items = (await client.get("/properties", headers=auth["headers"])).json()
    assert len(items) == 2


async def test_get_property_has_summary(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    resp = await client.get(f"/properties/{prop['id']}", headers=auth["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert data["summary"]["total_invested"] == prop["purchase_price"]


async def test_get_nonexistent_property_is_404(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    fake = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/properties/{fake}", headers=auth["headers"])).status_code == 404


async def test_get_other_users_property_is_404(client: AsyncClient, auth: dict, second_auth: dict):
    await _enable_property(client, auth["headers"])
    await _enable_property(client, second_auth["headers"])
    prop = await _create_property(client, auth["headers"])
    assert (await client.get(f"/properties/{prop['id']}", headers=second_auth["headers"])).status_code == 404


async def test_update_property(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    resp = await client.put(f"/properties/{prop['id']}", json={"name": "Renamed"}, headers=auth["headers"])
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


async def test_sell_property_via_update(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    resp = await client.put(
        f"/properties/{prop['id']}",
        json={"status": "sold", "sale_date": "2026-01-01", "sale_price": "8000000.00"},
        headers=auth["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sold"
    assert data["summary"]["profit"] is not None


async def test_delete_property_returns_204(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    assert (await client.delete(f"/properties/{prop['id']}", headers=auth["headers"])).status_code == 204


async def test_delete_property_cascades_transactions(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    await _create_tx(client, auth["headers"], prop["id"], TX_RENT)
    await client.delete(f"/properties/{prop['id']}", headers=auth["headers"])
    assert (await client.get(f"/properties/{prop['id']}", headers=auth["headers"])).status_code == 404


async def test_list_scoped_to_user(client: AsyncClient, auth: dict, second_auth: dict):
    await _enable_property(client, auth["headers"])
    await _enable_property(client, second_auth["headers"])
    await _create_property(client, auth["headers"])
    items = (await client.get("/properties", headers=second_auth["headers"])).json()
    assert len(items) == 0


# ── Transaction CRUD ──────────────────────────────────────────────────────────

async def test_create_monthly_transaction(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    resp = await client.post(f"/properties/{prop['id']}/transactions", json=TX_RENT, headers=auth["headers"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "income"
    assert data["billing_cycle"] == "monthly"


async def test_create_one_time_transaction(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    resp = await client.post(f"/properties/{prop['id']}/transactions", json=TX_ONE_TIME, headers=auth["headers"])
    assert resp.status_code == 201


async def test_one_time_without_date_is_422(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    payload = {**TX_ONE_TIME, "transaction_date": None}
    resp = await client.post(f"/properties/{prop['id']}/transactions", json=payload, headers=auth["headers"])
    assert resp.status_code == 422


async def test_recurring_without_start_date_is_422(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    payload = {**TX_RENT, "start_date": None}
    resp = await client.post(f"/properties/{prop['id']}/transactions", json=payload, headers=auth["headers"])
    assert resp.status_code == 422


async def test_list_transactions(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    await _create_tx(client, auth["headers"], prop["id"], TX_RENT)
    await _create_tx(client, auth["headers"], prop["id"], TX_MORTGAGE)
    txs = (await client.get(f"/properties/{prop['id']}/transactions", headers=auth["headers"])).json()
    assert len(txs) == 2


async def test_get_transaction(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    tx = await _create_tx(client, auth["headers"], prop["id"], TX_RENT)
    resp = await client.get(f"/properties/{prop['id']}/transactions/{tx['id']}", headers=auth["headers"])
    assert resp.status_code == 200


async def test_get_transaction_wrong_property_is_404(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop1 = await _create_property(client, auth["headers"])
    prop2 = await _create_property(client, auth["headers"], {**PROPERTY, "name": "Other"})
    tx = await _create_tx(client, auth["headers"], prop1["id"], TX_RENT)
    assert (await client.get(
        f"/properties/{prop2['id']}/transactions/{tx['id']}", headers=auth["headers"]
    )).status_code == 404


async def test_update_transaction(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    tx = await _create_tx(client, auth["headers"], prop["id"], TX_RENT)
    resp = await client.put(
        f"/properties/{prop['id']}/transactions/{tx['id']}",
        json={"title": "Updated rent"},
        headers=auth["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated rent"


async def test_delete_transaction_returns_204(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    tx = await _create_tx(client, auth["headers"], prop["id"], TX_RENT)
    assert (await client.delete(
        f"/properties/{prop['id']}/transactions/{tx['id']}", headers=auth["headers"]
    )).status_code == 204


# ── Summary (total_summary service) ──────────────────────────────────────────

async def test_summary_total_invested_includes_one_time_expenses(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    await _create_tx(client, auth["headers"], prop["id"], TX_ONE_TIME)  # 100 000 expense one_time
    data = (await client.get(f"/properties/{prop['id']}", headers=auth["headers"])).json()
    expected = Decimal(prop["purchase_price"]) + Decimal("100000")
    assert Decimal(data["summary"]["total_invested"]) == expected


async def test_summary_profit_for_sold_property(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    await _create_tx(client, auth["headers"], prop["id"], TX_ONE_TIME)  # +100 000 expense
    await client.put(
        f"/properties/{prop['id']}",
        json={"status": "sold", "sale_date": "2026-01-01", "sale_price": "6000000.00"},
        headers=auth["headers"],
    )
    data = (await client.get(f"/properties/{prop['id']}", headers=auth["headers"])).json()
    # profit = sale_price - total_invested + total_income
    # = 6 000 000 - (5 000 000 + 100 000) + 0 = 900 000
    assert Decimal(data["summary"]["profit"]) == Decimal("900000")


async def test_summary_profit_none_when_active(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    data = (await client.get(f"/properties/{prop['id']}", headers=auth["headers"])).json()
    assert data["summary"]["profit"] is None


# ── Property analytics ────────────────────────────────────────────────────────

async def test_property_analytics_returns_12_months(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    resp = await client.get(f"/properties/{prop['id']}/analytics?year=2026", headers=auth["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["months"]) == 12
    assert data["year"] == 2026


async def test_property_analytics_income_in_active_months(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    # monthly rent starts 2020-02-01 → all months of 2020 from Feb onwards have income
    await _create_tx(client, auth["headers"], prop["id"], TX_RENT)
    resp = await client.get(f"/properties/{prop['id']}/analytics?year=2020", headers=auth["headers"])
    months = {m["month"]: m for m in resp.json()["months"]}
    assert Decimal(months[1]["income"]) == 0   # January — before start_date
    assert Decimal(months[2]["income"]) > 0    # February onwards
    assert Decimal(months[12]["income"]) > 0


async def test_property_analytics_one_time_in_correct_month(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    await _create_tx(client, auth["headers"], prop["id"], TX_ONE_TIME)  # date=2020-06-01
    resp = await client.get(f"/properties/{prop['id']}/analytics?year=2020", headers=auth["headers"])
    months = {m["month"]: m for m in resp.json()["months"]}
    assert Decimal(months[6]["expenses"]) == Decimal("100000")
    assert Decimal(months[5]["expenses"]) == 0
    assert Decimal(months[7]["expenses"]) == 0


async def test_property_analytics_missing_year_is_422(client: AsyncClient, auth: dict):
    await _enable_property(client, auth["headers"])
    prop = await _create_property(client, auth["headers"])
    assert (await client.get(f"/properties/{prop['id']}/analytics", headers=auth["headers"])).status_code == 422
