import uuid
from datetime import datetime

from pydantic import BaseModel


class UserSettingsOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    module_deposits: bool
    module_subscriptions: bool
    module_property: bool
    default_currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserSettingsUpdate(BaseModel):
    module_deposits: bool | None = None
    module_subscriptions: bool | None = None
    module_property: bool | None = None
    default_currency: str | None = None
