import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionFilter,
    SubscriptionOut,
    SubscriptionUpdate,
)
from app.services import subscription as svc

router = APIRouter(dependencies=[Depends(get_current_user)])


def _enrich(sub: Subscription) -> SubscriptionOut:
    return SubscriptionOut(
        **sub.__dict__,
        next_payment_date=svc.next_payment_date(sub),
        monthly_cost=svc.monthly_cost(sub),
    )


@router.get("", response_model=list[SubscriptionOut])
async def list_subscriptions(
    filter: SubscriptionFilter | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Subscription).where(Subscription.user_id == current_user.id)

    if filter == SubscriptionFilter.active:
        stmt = stmt.where(Subscription.is_active == True, Subscription.billing_cycle != "one_time")  # noqa: E712
    elif filter == SubscriptionFilter.cancelled:
        stmt = stmt.where(Subscription.is_active == False)  # noqa: E712
    elif filter == SubscriptionFilter.one_time:
        stmt = stmt.where(Subscription.billing_cycle == "one_time")

    result = await db.execute(stmt)
    return [_enrich(s) for s in result.scalars().all()]


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = Subscription(**body.model_dump(), user_id=current_user.id)
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return _enrich(sub)


async def _get_sub(sub_id: uuid.UUID, user: User, db: AsyncSession) -> Subscription:
    result = await db.execute(
        select(Subscription).where(Subscription.id == sub_id, Subscription.user_id == user.id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return sub


@router.get("/{sub_id}", response_model=SubscriptionOut)
async def get_subscription(
    sub_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return _enrich(await _get_sub(sub_id, current_user, db))


@router.put("/{sub_id}", response_model=SubscriptionOut)
async def update_subscription(
    sub_id: uuid.UUID,
    body: SubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await _get_sub(sub_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(sub, field, value)
    await db.commit()
    await db.refresh(sub)
    return _enrich(sub)


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    sub_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await _get_sub(sub_id, current_user, db)
    await db.delete(sub)
    await db.commit()
