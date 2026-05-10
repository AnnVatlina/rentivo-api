from datetime import date
from decimal import Decimal

from app.models.deposit import Deposit
from app.models.subscription import Subscription
from app.schemas.analytics import AnalyticsResponse, MonthlyBreakdown
from app.services import deposit as deposit_svc
from app.services import subscription as sub_svc


def _deposit_income_for_month(dep: Deposit, year: int, month: int) -> Decimal:
    month_start = date(year, month, 1)
    if month < 12:
        month_end = date(year, month + 1, 1)
    else:
        month_end = date(year + 1, 1, 1)

    if dep.open_date >= month_end:
        return Decimal("0")
    if dep.close_date and dep.close_date <= month_start:
        return Decimal("0")

    end_of_period = min(month_end, dep.close_date) if dep.close_date else month_end
    start_of_period = max(month_start, dep.open_date)

    income_to_end = dep.amount * (dep.annual_rate / Decimal("100")) * (
        Decimal((end_of_period - dep.open_date).days) / Decimal("365")
    )
    income_to_start = dep.amount * (dep.annual_rate / Decimal("100")) * (
        Decimal(max((start_of_period - dep.open_date).days, 0)) / Decimal("365")
    )
    return income_to_end - income_to_start


def _subscription_cost_for_month(sub: Subscription, year: int, month: int) -> Decimal:
    if not sub.is_active:
        return Decimal("0")

    month_start = date(year, month, 1)
    if month < 12:
        month_end = date(year, month + 1, 1)
    else:
        month_end = date(year + 1, 1, 1)

    if sub.start_date >= month_end:
        return Decimal("0")
    if sub.end_date and sub.end_date < month_start:
        return Decimal("0")
    if sub.billing_cycle == "one_time":
        if month_start <= sub.start_date < month_end:
            return sub.amount
        return Decimal("0")

    return sub_svc.monthly_cost(sub)


def build_analytics(
    deposits: list[Deposit],
    subscriptions: list[Subscription],
    year: int,
    currency: str,
) -> AnalyticsResponse:
    today = date.today()
    months = []

    for month in range(1, 13):
        is_projected = date(year, month, 1) > today

        dep_income = sum(
            (_deposit_income_for_month(d, year, month) for d in deposits if d.currency == currency),
            Decimal("0"),
        )
        sub_expenses = sum(
            (_subscription_cost_for_month(s, year, month) for s in subscriptions if s.currency == currency),
            Decimal("0"),
        )

        months.append(
            MonthlyBreakdown(
                month=month,
                year=year,
                deposit_income=round(dep_income, 2),
                subscription_expenses=round(sub_expenses, 2),
                net=round(dep_income - sub_expenses, 2),
                is_projected=is_projected,
            )
        )

    return AnalyticsResponse(year=year, currency=currency, months=months)
