from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.deposit import Deposit
from app.models.property import Property
from app.models.property_transaction import PropertyTransaction
from app.models.subscription import Subscription
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.analytics import AnalyticsResponse
from app.schemas.deposit import Currency
from app.services.analytics import build_analytics

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=AnalyticsResponse)
async def get_analytics(
    year: int = Query(..., ge=2000, le=2100),
    currency: Currency = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deposits = list((
        await db.execute(select(Deposit).where(Deposit.user_id == current_user.id))
    ).scalars().all())

    subscriptions = list((
        await db.execute(select(Subscription).where(Subscription.user_id == current_user.id))
    ).scalars().all())

    settings = (
        await db.execute(select(UserSettings).where(UserSettings.user_id == current_user.id))
    ).scalar_one_or_none()

    properties = list((
        await db.execute(select(Property).where(Property.user_id == current_user.id))
    ).scalars().all())

    prop_ids = [p.id for p in properties]
    property_transactions = []
    if prop_ids:
        property_transactions = list((
            await db.execute(
                select(PropertyTransaction).where(PropertyTransaction.property_id.in_(prop_ids))
            )
        ).scalars().all())

    return build_analytics(
        deposits=deposits,
        subscriptions=subscriptions,
        properties=properties,
        property_transactions=property_transactions,
        settings=settings,
        year=year,
        currency=currency.value,
    )
