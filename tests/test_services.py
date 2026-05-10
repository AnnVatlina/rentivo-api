from datetime import date
from decimal import Decimal

import pytest

from app.models.deposit import Deposit
from app.models.subscription import Subscription
from app.services import deposit as dep_svc
from app.services import subscription as sub_svc


# ─── Deposit service ───────────────────────────────────────────────────────────

def _deposit(**kwargs) -> Deposit:
    defaults = dict(
        title="Test",
        bank_name=None,
        currency="RUB",
    )
    defaults.update(kwargs)
    return Deposit(**defaults)


def test_income_zero_days():
    d = _deposit(amount=Decimal("100000"), annual_rate=Decimal("17"), open_date=date(2026, 1, 1), close_date=None)
    assert dep_svc.income_to_date(d, today=date(2026, 1, 1)) == Decimal("0")


def test_income_one_year_open():
    d = _deposit(amount=Decimal("365000"), annual_rate=Decimal("10"), open_date=date(2025, 1, 1), close_date=None)
    income = dep_svc.income_to_date(d, today=date(2026, 1, 1))
    # 365000 * 0.10 * 365/365 = 36500
    assert income == Decimal("36500")


def test_income_capped_at_close_date():
    d = _deposit(
        amount=Decimal("100000"), annual_rate=Decimal("10"),
        open_date=date(2026, 1, 1), close_date=date(2026, 4, 11),
    )
    # cap at close_date even if today is later
    income_capped = dep_svc.income_to_date(d, today=date(2026, 12, 31))
    income_at_close = dep_svc.income_to_date(d, today=date(2026, 4, 11))
    assert income_capped == income_at_close


def test_days_elapsed():
    d = _deposit(amount=Decimal("1"), annual_rate=Decimal("1"), open_date=date(2026, 1, 1), close_date=None)
    assert dep_svc.days_elapsed(d, today=date(2026, 1, 11)) == 10


# ─── Subscription service ──────────────────────────────────────────────────────

def _sub(**kwargs) -> Subscription:
    defaults = dict(
        title="Test",
        category=None,
        currency="USD",
        is_active=True,
        end_date=None,
    )
    defaults.update(kwargs)
    return Subscription(**defaults)


def test_monthly_cost_monthly():
    s = _sub(amount=Decimal("10"), billing_cycle="monthly")
    assert sub_svc.monthly_cost(s) == Decimal("10")


def test_monthly_cost_weekly():
    s = _sub(amount=Decimal("12"), billing_cycle="weekly")
    assert sub_svc.monthly_cost(s) == Decimal("12") * Decimal("52") / Decimal("12")


def test_monthly_cost_quarterly():
    s = _sub(amount=Decimal("30"), billing_cycle="quarterly")
    assert sub_svc.monthly_cost(s) == Decimal("10")


def test_monthly_cost_yearly():
    s = _sub(amount=Decimal("120"), billing_cycle="yearly")
    assert sub_svc.monthly_cost(s) == Decimal("10")


def test_monthly_cost_one_time():
    s = _sub(amount=Decimal("99"), billing_cycle="one_time")
    assert sub_svc.monthly_cost(s) == Decimal("0")


def test_next_payment_monthly_in_future():
    s = _sub(amount=Decimal("10"), billing_cycle="monthly", start_date=date(2026, 1, 15))
    nxt = sub_svc.next_payment_date(s, today=date(2026, 3, 1))
    assert nxt == date(2026, 3, 15)


def test_next_payment_inactive():
    s = _sub(amount=Decimal("10"), billing_cycle="monthly", start_date=date(2026, 1, 1), is_active=False)
    assert sub_svc.next_payment_date(s) is None


def test_next_payment_past_end_date():
    s = _sub(
        amount=Decimal("10"), billing_cycle="monthly",
        start_date=date(2025, 1, 1), end_date=date(2025, 6, 1),
    )
    assert sub_svc.next_payment_date(s, today=date(2026, 1, 1)) is None


def test_next_payment_one_time_in_future():
    s = _sub(amount=Decimal("10"), billing_cycle="one_time", start_date=date(2026, 12, 1))
    assert sub_svc.next_payment_date(s, today=date(2026, 5, 1)) == date(2026, 12, 1)


def test_next_payment_one_time_past():
    s = _sub(amount=Decimal("10"), billing_cycle="one_time", start_date=date(2025, 1, 1))
    assert sub_svc.next_payment_date(s, today=date(2026, 5, 1)) is None
