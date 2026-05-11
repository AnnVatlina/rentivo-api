import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_module
from app.database import get_db
from app.models.property import Property
from app.models.property_transaction import PropertyTransaction
from app.models.user import User
from app.schemas.property import (
    PropertyAnalyticsMonth,
    PropertyAnalyticsResponse,
    PropertyCreate,
    PropertyOut,
    PropertySummary,
    PropertyUpdate,
)
from app.schemas.property_transaction import (
    PropertyTransactionCreate,
    PropertyTransactionOut,
    PropertyTransactionUpdate,
)
from app.services import property as svc

router = APIRouter(dependencies=[Depends(get_current_user), Depends(require_module("property"))])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_property(prop_id: uuid.UUID, user: User, db: AsyncSession) -> Property:
    result = await db.execute(
        select(Property).where(Property.id == prop_id, Property.user_id == user.id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return prop


async def _get_transaction(
    prop_id: uuid.UUID, tid: uuid.UUID, user: User, db: AsyncSession
) -> PropertyTransaction:
    await _get_property(prop_id, user, db)  # ensures ownership
    result = await db.execute(
        select(PropertyTransaction).where(
            PropertyTransaction.id == tid,
            PropertyTransaction.property_id == prop_id,
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return tx


async def _load_transactions(prop_id: uuid.UUID, db: AsyncSession) -> list[PropertyTransaction]:
    result = await db.execute(
        select(PropertyTransaction).where(PropertyTransaction.property_id == prop_id)
    )
    return list(result.scalars().all())


def _enrich(prop: Property, transactions: list[PropertyTransaction] | None = None) -> PropertyOut:
    summary = None
    if transactions is not None:
        s = svc.total_summary(prop, transactions)
        summary = PropertySummary(**s)
    return PropertyOut(**prop.__dict__, summary=summary)


# ── Property CRUD ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[PropertyOut])
async def list_properties(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Property).where(Property.user_id == current_user.id))
    return [_enrich(p) for p in result.scalars().all()]


@router.post("", response_model=PropertyOut, status_code=status.HTTP_201_CREATED)
async def create_property(
    body: PropertyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prop = Property(**body.model_dump(), user_id=current_user.id)
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return _enrich(prop)


@router.get("/{prop_id}", response_model=PropertyOut)
async def get_property(
    prop_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prop = await _get_property(prop_id, current_user, db)
    txs = await _load_transactions(prop_id, db)
    return _enrich(prop, txs)


@router.put("/{prop_id}", response_model=PropertyOut)
async def update_property(
    prop_id: uuid.UUID,
    body: PropertyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prop = await _get_property(prop_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(prop, field, value)
    await db.commit()
    await db.refresh(prop)
    txs = await _load_transactions(prop_id, db)
    return _enrich(prop, txs)


@router.delete("/{prop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    prop_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prop = await _get_property(prop_id, current_user, db)
    await db.delete(prop)
    await db.commit()


# ── Transaction CRUD ──────────────────────────────────────────────────────────

@router.get("/{prop_id}/transactions", response_model=list[PropertyTransactionOut])
async def list_transactions(
    prop_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_property(prop_id, current_user, db)
    return list((await db.execute(
        select(PropertyTransaction).where(PropertyTransaction.property_id == prop_id)
    )).scalars().all())


@router.post("/{prop_id}/transactions", response_model=PropertyTransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    prop_id: uuid.UUID,
    body: PropertyTransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_property(prop_id, current_user, db)
    tx = PropertyTransaction(**body.model_dump(exclude_unset=False), property_id=prop_id)
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


@router.get("/{prop_id}/transactions/{tid}", response_model=PropertyTransactionOut)
async def get_transaction(
    prop_id: uuid.UUID,
    tid: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_transaction(prop_id, tid, current_user, db)


@router.put("/{prop_id}/transactions/{tid}", response_model=PropertyTransactionOut)
async def update_transaction(
    prop_id: uuid.UUID,
    tid: uuid.UUID,
    body: PropertyTransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tx = await _get_transaction(prop_id, tid, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tx, field, value)
    await db.commit()
    await db.refresh(tx)
    return tx


@router.delete("/{prop_id}/transactions/{tid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    prop_id: uuid.UUID,
    tid: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tx = await _get_transaction(prop_id, tid, current_user, db)
    await db.delete(tx)
    await db.commit()


# ── Property analytics ────────────────────────────────────────────────────────

@router.get("/{prop_id}/analytics", response_model=PropertyAnalyticsResponse)
async def get_property_analytics(
    prop_id: uuid.UUID,
    year: int = Query(..., ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prop = await _get_property(prop_id, current_user, db)
    txs = await _load_transactions(prop_id, db)
    today = date.today()
    months = []
    for month in range(1, 13):
        cf = svc.monthly_cashflow(txs, year, month, prop.currency)
        months.append(PropertyAnalyticsMonth(
            month=month,
            income=round(cf["income"], 2),
            expenses=round(cf["expenses"], 2),
            net=round(cf["net"], 2),
            is_projected=date(year, month, 1) > today,
        ))
    return PropertyAnalyticsResponse(
        property_id=prop_id,
        year=year,
        currency=prop.currency,
        months=months,
    )
