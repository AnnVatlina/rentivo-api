from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.deposit import Deposit
from app.models.subscription import Subscription
from app.models.user import User
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
    deposits = (
        await db.execute(select(Deposit).where(Deposit.user_id == current_user.id))
    ).scalars().all()

    subscriptions = (
        await db.execute(select(Subscription).where(Subscription.user_id == current_user.id))
    ).scalars().all()

    return build_analytics(list(deposits), list(subscriptions), year, currency.value)
