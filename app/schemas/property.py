import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class PropertyStatus(str, Enum):
    active = "active"
    sold = "sold"


class PropertyCreate(BaseModel):
    name: str
    address: str | None = None
    purchase_date: date
    purchase_price: Decimal = Field(gt=0)
    currency: str  # reuses Currency enum from deposit schemas at runtime validation
    status: PropertyStatus = PropertyStatus.active
    sale_date: date | None = None
    sale_price: Decimal | None = Field(default=None, gt=0)
    sale_notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def check_sold_fields(cls, values):
        status = values.get("status")
        if status == "sold" or status == PropertyStatus.sold:
            if not values.get("sale_date"):
                raise ValueError("sale_date is required when status is 'sold'")
            if not values.get("sale_price"):
                raise ValueError("sale_price is required when status is 'sold'")
        return values


class PropertyUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    purchase_date: date | None = None
    purchase_price: Decimal | None = Field(default=None, gt=0)
    currency: str | None = None
    status: PropertyStatus | None = None
    sale_date: date | None = None
    sale_price: Decimal | None = Field(default=None, gt=0)
    sale_notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def check_sold_fields(cls, values):
        status = values.get("status")
        if status == "sold" or status == PropertyStatus.sold:
            if not values.get("sale_date"):
                raise ValueError("sale_date is required when status is 'sold'")
            if not values.get("sale_price"):
                raise ValueError("sale_price is required when status is 'sold'")
        return values


class PropertySummary(BaseModel):
    total_invested: Decimal
    total_income: Decimal
    total_expenses: Decimal
    profit: Decimal | None  # None if not sold


class PropertyOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    address: str | None
    purchase_date: date
    purchase_price: Decimal
    currency: str
    status: str
    sale_date: date | None
    sale_price: Decimal | None
    sale_notes: str | None
    created_at: datetime
    summary: PropertySummary | None = None  # populated on detail endpoint

    model_config = {"from_attributes": True}


class PropertyAnalyticsMonth(BaseModel):
    month: int
    income: Decimal
    expenses: Decimal
    net: Decimal
    is_projected: bool


class PropertyAnalyticsResponse(BaseModel):
    property_id: uuid.UUID
    year: int
    currency: str
    months: list[PropertyAnalyticsMonth]
