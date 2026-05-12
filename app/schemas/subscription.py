import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.deposit import Currency


class BillingCycle(str, Enum):
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"
    biennial = "biennial"
    one_time = "one_time"


class SubscriptionCreate(BaseModel):
    title: str
    category: str | None = None
    amount: Decimal = Field(gt=0)
    currency: Currency
    billing_cycle: BillingCycle
    start_date: date
    end_date: date | None = None
    is_active: bool = True


class SubscriptionUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: Currency | None = None
    billing_cycle: BillingCycle | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    category: str | None
    amount: Decimal
    currency: str
    billing_cycle: str
    start_date: date
    end_date: date | None
    is_active: bool
    created_at: datetime
    next_payment_date: date | None
    monthly_cost: Decimal

    model_config = {"from_attributes": True}


class SubscriptionFilter(str, Enum):
    active = "active"
    cancelled = "cancelled"
    one_time = "one_time"
