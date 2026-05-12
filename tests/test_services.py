from datetime import date
from decimal import Decimal

import pytest

from app.models.deposit import Deposit
from app.models.property import Property
from app.models.property_transaction import PropertyTransaction
from app.models.subscription import Subscription
from app.services import deposit as dep_svc
from app.services import property as prop_svc
from app.services import subscription as sub_svc
from app.services.analytics import _subscription_cost_for_month


# ─── Deposit service ───────────────────────────────────────────────────────────

def _deposit(**kwargs) -> Deposit:
    defaults = dict(
        title="Test",
        bank_name=None,
        currency="RUB",
        interest_type="simple",
        compound_frequency=None,
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


def test_compound_income_greater_than_simple():
    # use monthly compounding — more periods than simple interest → higher income
    simple = _deposit(amount=Decimal("100000"), annual_rate=Decimal("10"),
                      open_date=date(2025, 1, 1), close_date=None,
                      interest_type="simple", compound_frequency=None)
    compound = _deposit(amount=Decimal("100000"), annual_rate=Decimal("10"),
                        open_date=date(2025, 1, 1), close_date=None,
                        interest_type="compound", compound_frequency="monthly")
    today = date(2026, 1, 1)
    assert dep_svc.income_to_date(compound, today=today) > dep_svc.income_to_date(simple, today=today)


def test_compound_annually_one_year():
    # A = 100000 * (1 + 0.10/1)^1 = 110000, income = 10000
    d = _deposit(amount=Decimal("100000"), annual_rate=Decimal("10"),
                 open_date=date(2025, 1, 1), close_date=None,
                 interest_type="compound", compound_frequency="annually")
    income = dep_svc.income_to_date(d, today=date(2026, 1, 1))
    assert abs(income - Decimal("10000")) < Decimal("1")


def test_compound_zero_days_is_zero():
    d = _deposit(amount=Decimal("100000"), annual_rate=Decimal("10"),
                 open_date=date(2026, 1, 1), close_date=None,
                 interest_type="compound", compound_frequency="monthly")
    assert dep_svc.income_to_date(d, today=date(2026, 1, 1)) == Decimal("0")


def test_compound_capped_at_close_date():
    d = _deposit(amount=Decimal("100000"), annual_rate=Decimal("10"),
                 open_date=date(2026, 1, 1), close_date=date(2026, 4, 11),
                 interest_type="compound", compound_frequency="monthly")
    income_capped = dep_svc.income_to_date(d, today=date(2026, 12, 31))
    income_at_close = dep_svc.income_to_date(d, today=date(2026, 4, 11))
    assert income_capped == income_at_close


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


# ─── Property service ──────────────────────────────────────────────────────────

def _prop(**kwargs) -> Property:
    defaults = dict(
        name="Test", address=None, currency="RUB",
        status="active", sale_date=None, sale_price=None, sale_notes=None,
    )
    defaults.update(kwargs)
    return Property(**defaults)


def _tx(**kwargs) -> PropertyTransaction:
    defaults = dict(
        title="Tx", currency="RUB",
        transaction_date=None, start_date=None, end_date=None,
    )
    defaults.update(kwargs)
    return PropertyTransaction(**defaults)


def test_monthly_cashflow_monthly_income():
    tx = _tx(type="income", category="rent", amount=Decimal("50000"),
              billing_cycle="monthly", start_date=date(2026, 1, 1))
    cf = prop_svc.monthly_cashflow([tx], 2026, 3, "RUB")
    assert cf["income"] == Decimal("50000")
    assert cf["expenses"] == Decimal("0")


def test_monthly_cashflow_one_time_in_month():
    tx = _tx(type="expense", category="maintenance", amount=Decimal("100000"),
              billing_cycle="one_time", transaction_date=date(2026, 6, 15))
    cf = prop_svc.monthly_cashflow([tx], 2026, 6, "RUB")
    assert cf["expenses"] == Decimal("100000")


def test_monthly_cashflow_one_time_wrong_month():
    tx = _tx(type="expense", category="maintenance", amount=Decimal("100000"),
              billing_cycle="one_time", transaction_date=date(2026, 6, 15))
    assert prop_svc.monthly_cashflow([tx], 2026, 7, "RUB")["expenses"] == Decimal("0")


def test_monthly_cashflow_before_start_date():
    tx = _tx(type="income", category="rent", amount=Decimal("50000"),
              billing_cycle="monthly", start_date=date(2026, 3, 1))
    assert prop_svc.monthly_cashflow([tx], 2026, 2, "RUB")["income"] == Decimal("0")


def test_monthly_cashflow_after_end_date():
    tx = _tx(type="income", category="rent", amount=Decimal("50000"),
              billing_cycle="monthly", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31))
    assert prop_svc.monthly_cashflow([tx], 2026, 4, "RUB")["income"] == Decimal("0")


def test_monthly_cashflow_currency_filter():
    tx = _tx(type="income", category="rent", amount=Decimal("500"),
              billing_cycle="monthly", start_date=date(2026, 1, 1), currency="USD")
    assert prop_svc.monthly_cashflow([tx], 2026, 1, "RUB")["income"] == Decimal("0")


def test_total_summary_no_transactions():
    prop = _prop(purchase_price=Decimal("5000000"), purchase_date=date(2020, 1, 1))
    s = prop_svc.total_summary(prop, [])
    assert s["total_invested"] == Decimal("5000000")
    assert s["profit"] is None


def test_total_summary_profit_when_sold():
    prop = _prop(purchase_price=Decimal("5000000"), purchase_date=date(2020, 1, 1),
                 status="sold", sale_price=Decimal("7000000"))
    s = prop_svc.total_summary(prop, [])
    # profit = 7000000 - 5000000 + 0 = 2000000
    assert s["profit"] == Decimal("2000000")


def test_total_summary_one_time_expense_adds_to_invested():
    prop = _prop(purchase_price=Decimal("5000000"), purchase_date=date(2020, 1, 1),
                 status="sold", sale_price=Decimal("6000000"))
    tx = _tx(type="expense", category="maintenance", amount=Decimal("200000"),
             billing_cycle="one_time", transaction_date=date(2021, 1, 1))
    s = prop_svc.total_summary(prop, [tx])
    assert s["total_invested"] == Decimal("5200000")
    assert s["profit"] == Decimal("800000")


# ─── Analytics: subscription cost per month ────────────────────────────────────

def _asub(**kwargs) -> Subscription:
    defaults = dict(title="T", category=None, currency="USD", is_active=True, end_date=None)
    defaults.update(kwargs)
    return Subscription(**defaults)


def test_analytics_yearly_shows_full_amount_in_payment_month():
    # start_date May 15 → annual payment on May 15 every year
    s = _asub(amount=Decimal("120"), billing_cycle="yearly", start_date=date(2025, 5, 15))
    assert _subscription_cost_for_month(s, 2026, 5) == Decimal("120")


def test_analytics_yearly_zero_in_non_payment_month():
    s = _asub(amount=Decimal("120"), billing_cycle="yearly", start_date=date(2025, 5, 15))
    assert _subscription_cost_for_month(s, 2026, 4) == Decimal("0")
    assert _subscription_cost_for_month(s, 2026, 6) == Decimal("0")


def test_analytics_quarterly_shows_full_amount_in_payment_months():
    # start Jan 1 → payments Jan 1, Apr 1, Jul 1, Oct 1
    s = _asub(amount=Decimal("30"), billing_cycle="quarterly", start_date=date(2026, 1, 1))
    assert _subscription_cost_for_month(s, 2026, 1) == Decimal("30")
    assert _subscription_cost_for_month(s, 2026, 4) == Decimal("30")
    assert _subscription_cost_for_month(s, 2026, 2) == Decimal("0")


def test_analytics_monthly_shows_amount_every_active_month():
    s = _asub(amount=Decimal("15"), billing_cycle="monthly", start_date=date(2026, 1, 1))
    for m in range(1, 13):
        assert _subscription_cost_for_month(s, 2026, m) == Decimal("15")


def test_analytics_yearly_respects_end_date():
    # end_date before payment would land → 0
    s = _asub(amount=Decimal("120"), billing_cycle="yearly",
              start_date=date(2025, 5, 15), end_date=date(2026, 5, 1))
    assert _subscription_cost_for_month(s, 2026, 5) == Decimal("0")


def test_analytics_inactive_subscription_always_zero():
    s = _asub(amount=Decimal("120"), billing_cycle="yearly",
              start_date=date(2025, 5, 15), is_active=False)
    assert _subscription_cost_for_month(s, 2026, 5) == Decimal("0")
