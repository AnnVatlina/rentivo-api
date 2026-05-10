import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    RUB = "RUB"
    GEL = "GEL"
    BYN = "BYN"


class DepositCreate(BaseModel):
    title: str
    bank_name: str | None = None
    amount: Decimal = Field(gt=0)
    currency: Currency
    open_date: date
    close_date: date | None = None
    annual_rate: Decimal = Field(gt=0)


class DepositUpdate(BaseModel):
    title: str | None = None
    bank_name: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: Currency | None = None
    open_date: date | None = None
    close_date: date | None = None
    annual_rate: Decimal | None = Field(default=None, gt=0)


class DepositOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    bank_name: str | None
    amount: Decimal
    currency: str
    open_date: date
    close_date: date | None
    annual_rate: Decimal
    created_at: datetime
    income_to_date: Decimal
    days_elapsed: int

    model_config = {"from_attributes": True}
