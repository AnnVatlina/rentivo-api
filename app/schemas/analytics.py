from decimal import Decimal

from pydantic import BaseModel


class MonthlyBreakdown(BaseModel):
    month: int
    year: int
    deposit_income: Decimal | None
    subscription_expenses: Decimal | None
    property_income: Decimal | None
    property_expenses: Decimal | None
    net: Decimal
    is_projected: bool


class AnalyticsResponse(BaseModel):
    year: int
    currency: str
    deposit_currency: str | None = None
    subscription_currency: str | None = None
    months: list[MonthlyBreakdown]
