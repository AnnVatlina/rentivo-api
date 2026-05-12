from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from app.models.subscription import Subscription


def monthly_cost(sub: Subscription) -> Decimal:
    cycle = sub.billing_cycle
    amount = sub.amount
    if cycle == "weekly":
        return amount * Decimal("52") / Decimal("12")
    if cycle == "monthly":
        return amount
    if cycle == "quarterly":
        return amount / Decimal("3")
    if cycle == "yearly":
        return amount / Decimal("12")
    if cycle == "biennial":
        return amount / Decimal("24")
    return Decimal("0")  # one_time


def next_payment_date(sub: Subscription, today: date | None = None) -> date | None:
    today = today or date.today()

    if not sub.is_active:
        return None
    if sub.end_date and sub.end_date < today:
        return None
    if sub.billing_cycle == "one_time":
        return sub.start_date if sub.start_date >= today else None

    delta_map = {
        "weekly": relativedelta(weeks=1),
        "monthly": relativedelta(months=1),
        "quarterly": relativedelta(months=3),
        "yearly": relativedelta(years=1),
        "biennial": relativedelta(years=2),
    }
    delta = delta_map[sub.billing_cycle]

    candidate = sub.start_date
    while candidate < today:
        candidate += delta

    if sub.end_date and candidate > sub.end_date:
        return None
    return candidate
