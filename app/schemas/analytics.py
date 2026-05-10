from decimal import Decimal

from pydantic import BaseModel


class MonthlyBreakdown(BaseModel):
    month: int
    year: int
    deposit_income: Decimal
    subscription_expenses: Decimal
    net: Decimal
    is_projected: bool


class AnalyticsResponse(BaseModel):
    year: int
    currency: str
    months: list[MonthlyBreakdown]
