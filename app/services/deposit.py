from datetime import date
from decimal import Decimal

from app.models.deposit import Deposit


def income_to_date(deposit: Deposit, today: date | None = None) -> Decimal:
    today = today or date.today()
    end = min(today, deposit.close_date) if deposit.close_date else today
    days = max((end - deposit.open_date).days, 0)
    return deposit.amount * (deposit.annual_rate / Decimal("100")) * (Decimal(days) / Decimal("365"))


def days_elapsed(deposit: Deposit, today: date | None = None) -> int:
    today = today or date.today()
    end = min(today, deposit.close_date) if deposit.close_date else today
    return max((end - deposit.open_date).days, 0)
