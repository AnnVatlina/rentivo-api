from datetime import date
from decimal import Decimal

from app.models.deposit import Deposit

_COMPOUND_N = {"daily": 365, "monthly": 12, "quarterly": 4, "annually": 1}


def income_to_date(deposit: Deposit, today: date | None = None) -> Decimal:
    today = today or date.today()
    end = min(today, deposit.close_date) if deposit.close_date else today
    days = max((end - deposit.open_date).days, 0)
    if days == 0:
        return Decimal("0")

    if deposit.interest_type == "compound":
        n = _COMPOUND_N.get(deposit.compound_frequency or "annually", 1)
        t = Decimal(days) / Decimal("365")
        r = deposit.annual_rate / Decimal("100")
        a = deposit.amount * (1 + r / n) ** (n * t)
        return a - deposit.amount

    # simple interest
    return deposit.amount * (deposit.annual_rate / Decimal("100")) * (Decimal(days) / Decimal("365"))


def days_elapsed(deposit: Deposit, today: date | None = None) -> int:
    today = today or date.today()
    end = min(today, deposit.close_date) if deposit.close_date else today
    return max((end - deposit.open_date).days, 0)
