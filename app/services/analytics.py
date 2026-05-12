from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from app.models.deposit import Deposit
from app.models.property import Property
from app.models.property_transaction import PropertyTransaction
from app.models.subscription import Subscription
from app.models.user_settings import UserSettings
from app.schemas.analytics import AnalyticsResponse, MonthlyBreakdown
from app.services import deposit as deposit_svc
from app.services import subscription as sub_svc
from app.services import property as prop_svc

_BILLING_DELTA = {
    "weekly":    relativedelta(weeks=1),
    "quarterly": relativedelta(months=3),
    "yearly":    relativedelta(years=1),
    "biennial":  relativedelta(years=2),
}


def _deposit_income_for_month(dep: Deposit, year: int, month: int) -> Decimal:
    month_start = date(year, month, 1)
    month_end = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)

    if dep.open_date >= month_end:
        return Decimal("0")
    if dep.close_date and dep.close_date <= month_start:
        return Decimal("0")

    return deposit_svc.income_to_date(dep, today=month_end) - deposit_svc.income_to_date(dep, today=month_start)


def _subscription_cost_for_month(sub: Subscription, year: int, month: int) -> Decimal:
    if not sub.is_active:
        return Decimal("0")

    month_start = date(year, month, 1)
    month_end = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)

    if sub.start_date >= month_end:
        return Decimal("0")
    if sub.end_date and sub.end_date < month_start:
        return Decimal("0")

    if sub.billing_cycle == "one_time":
        return sub.amount if month_start <= sub.start_date < month_end else Decimal("0")

    if sub.billing_cycle == "monthly":
        # Monthly: already one payment per month, show the amount directly
        return sub.amount

    # weekly / quarterly / yearly — show the full payment amount only in months
    # where a payment actually lands (same logic as next_payment_date).
    delta = _BILLING_DELTA[sub.billing_cycle]
    candidate = sub.start_date
    # Advance to first payment date that is >= month_start
    while candidate < month_start:
        candidate += delta

    total = Decimal("0")
    while candidate < month_end:
        if sub.end_date is None or candidate <= sub.end_date:
            total += sub.amount
        candidate += delta
    return total


def build_analytics(
    deposits: list[Deposit],
    subscriptions: list[Subscription],
    properties: list[Property],
    property_transactions: list[PropertyTransaction],
    settings: UserSettings | None,
    year: int,
    currency: str,
) -> AnalyticsResponse:
    today = date.today()
    deposits_on = settings is None or settings.module_deposits
    subs_on = settings is None or settings.module_subscriptions
    prop_on = settings is None or settings.module_property

    months = []
    for month in range(1, 13):
        is_projected = date(year, month, 1) > today

        dep_income: Decimal | None = None
        if deposits_on:
            dep_income = round(sum(
                (_deposit_income_for_month(d, year, month) for d in deposits if d.currency == currency),
                Decimal("0"),
            ), 2)

        sub_expenses: Decimal | None = None
        if subs_on:
            sub_expenses = round(sum(
                (_subscription_cost_for_month(s, year, month) for s in subscriptions if s.currency == currency),
                Decimal("0"),
            ), 2)

        prop_income: Decimal | None = None
        prop_expenses: Decimal | None = None
        if prop_on:
            prop_income = Decimal("0")
            prop_expenses = Decimal("0")
            for prop in properties:
                txs = [t for t in property_transactions if t.property_id == prop.id]
                cf = prop_svc.monthly_cashflow(txs, year, month, currency)
                prop_income += cf["income"]
                prop_expenses += cf["expenses"]
            prop_income = round(prop_income, 2)
            prop_expenses = round(prop_expenses, 2)

        net = Decimal("0")
        if dep_income is not None:
            net += dep_income
        if sub_expenses is not None:
            net -= sub_expenses
        if prop_income is not None:
            net += prop_income
        if prop_expenses is not None:
            net -= prop_expenses

        months.append(MonthlyBreakdown(
            month=month,
            year=year,
            deposit_income=dep_income,
            subscription_expenses=sub_expenses,
            property_income=prop_income,
            property_expenses=prop_expenses,
            net=round(net, 2),
            is_projected=is_projected,
        ))

    return AnalyticsResponse(year=year, currency=currency, months=months)
