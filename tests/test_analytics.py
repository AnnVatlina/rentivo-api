"""Integration tests for GET /analytics."""
import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient


def _dec(val) -> Decimal:
    return Decimal(str(val))


# ── Auth guard ────────────────────────────────────────────────────────────────

async def test_requires_auth(client: AsyncClient):
    assert (await client.get("/analytics?year=2026&currency=RUB")).status_code == 403


async def test_invalid_token_is_401(client: AsyncClient):
    assert (
        await client.get("/analytics?year=2026&currency=RUB", headers={"Authorization": "Bearer bad"})
    ).status_code == 401


# ── Parameter validation ──────────────────────────────────────────────────────

async def test_missing_year_is_422(client: AsyncClient, auth: dict):
    assert (await client.get("/analytics?currency=RUB", headers=auth["headers"])).status_code == 422


async def test_missing_currency_is_422(client: AsyncClient, auth: dict):
    assert (await client.get("/analytics?year=2026", headers=auth["headers"])).status_code == 422


async def test_invalid_currency_is_422(client: AsyncClient, auth: dict):
    assert (await client.get("/analytics?year=2026&currency=JPY", headers=auth["headers"])).status_code == 422


async def test_year_below_range_is_422(client: AsyncClient, auth: dict):
    assert (await client.get("/analytics?year=1999&currency=RUB", headers=auth["headers"])).status_code == 422


async def test_year_above_range_is_422(client: AsyncClient, auth: dict):
    assert (await client.get("/analytics?year=2101&currency=RUB", headers=auth["headers"])).status_code == 422


# ── Response structure ────────────────────────────────────────────────────────

async def test_returns_12_months(client: AsyncClient, auth: dict):
    resp = await client.get("/analytics?year=2026&currency=RUB", headers=auth["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 2026
    assert data["currency"] == "RUB"
    assert len(data["months"]) == 12
    months = [m["month"] for m in data["months"]]
    assert months == list(range(1, 13))


async def test_empty_data_all_zeros(client: AsyncClient, auth: dict):
    resp = await client.get("/analytics?year=2026&currency=RUB", headers=auth["headers"])
    for m in resp.json()["months"]:
        assert _dec(m["deposit_income"]) == 0
        assert _dec(m["subscription_expenses"]) == 0
        assert _dec(m["net"]) == 0


# ── Projected flag ────────────────────────────────────────────────────────────

async def test_past_months_are_not_projected(client: AsyncClient, auth: dict):
    """All months in 2020 must be actual (not projected)."""
    resp = await client.get("/analytics?year=2020&currency=RUB", headers=auth["headers"])
    for m in resp.json()["months"]:
        assert m["is_projected"] is False, f"month {m['month']} should not be projected"


async def test_future_months_are_projected(client: AsyncClient, auth: dict):
    """All months in 2099 must be projected."""
    resp = await client.get("/analytics?year=2099&currency=RUB", headers=auth["headers"])
    for m in resp.json()["months"]:
        assert m["is_projected"] is True, f"month {m['month']} should be projected"


async def test_current_year_splits_actual_and_projected(client: AsyncClient, auth: dict):
    today = datetime.date.today()
    resp = await client.get(f"/analytics?year={today.year}&currency=RUB", headers=auth["headers"])
    months = resp.json()["months"]
    past = [m for m in months if m["month"] < today.month]
    future = [m for m in months if m["month"] > today.month]
    assert all(not m["is_projected"] for m in past)
    assert all(m["is_projected"] for m in future)


# ── Deposit income ────────────────────────────────────────────────────────────

async def test_deposit_income_appears_in_correct_months(client: AsyncClient, auth: dict):
    """Deposit open Jan 1 – Mar 31 should earn income in Jan, Feb, Mar but not April."""
    await client.post("/deposits", json={
        "title": "Q1 deposit",
        "amount": "365000",
        "currency": "RUB",
        "open_date": "2020-01-01",
        "close_date": "2020-03-31",
        "annual_rate": "10.0",
    }, headers=auth["headers"])

    resp = await client.get("/analytics?year=2020&currency=RUB", headers=auth["headers"])
    months = {m["month"]: m for m in resp.json()["months"]}

    assert _dec(months[1]["deposit_income"]) > 0
    assert _dec(months[2]["deposit_income"]) > 0
    assert _dec(months[3]["deposit_income"]) > 0
    assert _dec(months[4]["deposit_income"]) == 0


async def test_deposit_income_net_equals_income_minus_expenses(client: AsyncClient, auth: dict):
    await client.post("/deposits", json={
        "title": "Deposit",
        "amount": "100000",
        "currency": "RUB",
        "open_date": "2020-01-01",
        "annual_rate": "12.0",
    }, headers=auth["headers"])

    months = (await client.get("/analytics?year=2020&currency=RUB", headers=auth["headers"])).json()["months"]
    for m in months:
        net = _dec(m["deposit_income"]) - _dec(m["subscription_expenses"])
        assert abs(net - _dec(m["net"])) < Decimal("0.01"), f"month {m['month']}: net mismatch"


# ── Subscription expenses ─────────────────────────────────────────────────────

async def test_subscription_expenses_appear_in_active_months(client: AsyncClient, auth: dict):
    """Monthly subscription active all of 2020 → every month has expenses."""
    await client.post("/subscriptions", json={
        "title": "Annual service",
        "amount": "120.00",
        "currency": "USD",
        "billing_cycle": "monthly",
        "start_date": "2020-01-01",
        "is_active": True,
    }, headers=auth["headers"])

    months = (await client.get("/analytics?year=2020&currency=USD", headers=auth["headers"])).json()["months"]
    for m in months:
        assert _dec(m["subscription_expenses"]) == Decimal("120.00"), (
            f"month {m['month']} expected 120.00"
        )


async def test_one_time_subscription_appears_in_start_month_only(client: AsyncClient, auth: dict):
    await client.post("/subscriptions", json={
        "title": "One-off",
        "amount": "99.00",
        "currency": "USD",
        "billing_cycle": "one_time",
        "start_date": "2020-06-15",
        "is_active": True,
    }, headers=auth["headers"])

    months = (await client.get("/analytics?year=2020&currency=USD", headers=auth["headers"])).json()["months"]
    month_map = {m["month"]: m for m in months}
    assert _dec(month_map[6]["subscription_expenses"]) == Decimal("99.00")
    assert _dec(month_map[5]["subscription_expenses"]) == 0
    assert _dec(month_map[7]["subscription_expenses"]) == 0


async def test_cancelled_subscription_cost_excluded(client: AsyncClient, auth: dict):
    """Inactive subscription must not appear in expenses."""
    await client.post("/subscriptions", json={
        "title": "Cancelled",
        "amount": "50.00",
        "currency": "USD",
        "billing_cycle": "monthly",
        "start_date": "2020-01-01",
        "is_active": False,
    }, headers=auth["headers"])

    months = (await client.get("/analytics?year=2020&currency=USD", headers=auth["headers"])).json()["months"]
    assert all(_dec(m["subscription_expenses"]) == 0 for m in months)


# ── Currency isolation ────────────────────────────────────────────────────────

async def test_currency_filter_excludes_other_currencies(client: AsyncClient, auth: dict):
    """A USD deposit must not appear in RUB analytics."""
    await client.post("/deposits", json={
        "title": "USD deposit",
        "amount": "100000",
        "currency": "USD",
        "open_date": "2020-01-01",
        "annual_rate": "10.0",
    }, headers=auth["headers"])

    months = (await client.get("/analytics?year=2020&currency=RUB", headers=auth["headers"])).json()["months"]
    assert all(_dec(m["deposit_income"]) == 0 for m in months)


async def test_currency_filter_includes_matching_currency(client: AsyncClient, auth: dict):
    await client.post("/deposits", json={
        "title": "EUR deposit",
        "amount": "10000",
        "currency": "EUR",
        "open_date": "2020-01-01",
        "annual_rate": "5.0",
    }, headers=auth["headers"])

    months = (await client.get("/analytics?year=2020&currency=EUR", headers=auth["headers"])).json()["months"]
    assert any(_dec(m["deposit_income"]) > 0 for m in months)


# ── User isolation ────────────────────────────────────────────────────────────

async def test_analytics_scoped_to_user(client: AsyncClient, auth: dict, second_auth: dict):
    """User A's deposit must not appear in User B's analytics."""
    await client.post("/deposits", json={
        "title": "Private deposit",
        "amount": "100000",
        "currency": "RUB",
        "open_date": "2020-01-01",
        "annual_rate": "10.0",
    }, headers=auth["headers"])

    months = (await client.get("/analytics?year=2020&currency=RUB", headers=second_auth["headers"])).json()["months"]
    assert all(_dec(m["deposit_income"]) == 0 for m in months)
