import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    RUB = "RUB"
    GEL = "GEL"
    BYN = "BYN"


class InterestType(str, Enum):
    simple = "simple"
    compound = "compound"


class CompoundFrequency(str, Enum):
    daily = "daily"
    monthly = "monthly"
    quarterly = "quarterly"
    annually = "annually"


def _validate_compound(values: dict) -> dict:
    interest_type = values.get("interest_type")
    compound_frequency = values.get("compound_frequency")
    if interest_type == InterestType.compound and compound_frequency is None:
        raise ValueError("compound_frequency is required when interest_type is 'compound'")
    if interest_type == InterestType.simple and compound_frequency is not None:
        raise ValueError("compound_frequency must be null when interest_type is 'simple'")
    return values


class DepositCreate(BaseModel):
    title: str
    bank_name: str | None = None
    amount: Decimal = Field(gt=0)
    currency: Currency
    open_date: date
    close_date: date | None = None
    annual_rate: Decimal = Field(gt=0)
    interest_type: InterestType = InterestType.simple
    compound_frequency: CompoundFrequency | None = None

    @model_validator(mode="before")
    @classmethod
    def check_compound(cls, values):
        return _validate_compound(values)


class DepositUpdate(BaseModel):
    title: str | None = None
    bank_name: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: Currency | None = None
    open_date: date | None = None
    close_date: date | None = None
    annual_rate: Decimal | None = Field(default=None, gt=0)
    interest_type: InterestType | None = None
    compound_frequency: CompoundFrequency | None = None

    @model_validator(mode="before")
    @classmethod
    def check_compound(cls, values):
        # Only validate when both fields are present in the update
        if "interest_type" in values or "compound_frequency" in values:
            return _validate_compound(values)
        return values


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
    interest_type: str
    compound_frequency: str | None
    created_at: datetime
    income_to_date: Decimal
    days_elapsed: int

    model_config = {"from_attributes": True}
