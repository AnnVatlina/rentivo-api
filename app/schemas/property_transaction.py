import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TransactionType(str, Enum):
    income = "income"
    expense = "expense"


class TransactionCategory(str, Enum):
    mortgage = "mortgage"
    utilities = "utilities"
    tax = "tax"
    maintenance = "maintenance"
    rent = "rent"
    other = "other"


class TransactionBillingCycle(str, Enum):
    one_time = "one_time"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


def _validate_dates(values: dict) -> dict:
    billing_cycle = values.get("billing_cycle")
    if billing_cycle == "one_time" or billing_cycle == TransactionBillingCycle.one_time:
        if not values.get("transaction_date"):
            raise ValueError("transaction_date is required for one_time billing_cycle")
    else:
        if billing_cycle is not None and not values.get("start_date"):
            raise ValueError("start_date is required for recurring billing_cycle")
    return values


class PropertyTransactionCreate(BaseModel):
    type: TransactionType
    category: TransactionCategory
    title: str
    amount: Decimal = Field(gt=0)
    currency: str
    billing_cycle: TransactionBillingCycle
    transaction_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def check_dates(cls, values):
        return _validate_dates(values)


class PropertyTransactionUpdate(BaseModel):
    type: TransactionType | None = None
    category: TransactionCategory | None = None
    title: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = None
    billing_cycle: TransactionBillingCycle | None = None
    transaction_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def check_dates(cls, values):
        if "billing_cycle" in values:
            return _validate_dates(values)
        return values


class PropertyTransactionOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    type: str
    category: str
    title: str
    amount: Decimal
    currency: str
    billing_cycle: str
    transaction_date: date | None
    start_date: date | None
    end_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}
