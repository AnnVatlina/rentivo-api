import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_module
from app.database import get_db
from app.models.deposit import Deposit
from app.models.user import User
from app.schemas.deposit import DepositCreate, DepositOut, DepositUpdate
from app.services import deposit as svc

router = APIRouter(dependencies=[Depends(get_current_user), Depends(require_module("deposits"))])


def _enrich(deposit: Deposit) -> DepositOut:
    return DepositOut(
        **deposit.__dict__,
        income_to_date=svc.income_to_date(deposit),
        days_elapsed=svc.days_elapsed(deposit),
    )


@router.get("", response_model=list[DepositOut])
async def list_deposits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Deposit).where(Deposit.user_id == current_user.id))
    return [_enrich(d) for d in result.scalars().all()]


@router.post("", response_model=DepositOut, status_code=status.HTTP_201_CREATED)
async def create_deposit(
    body: DepositCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deposit = Deposit(**body.model_dump(), user_id=current_user.id)
    db.add(deposit)
    await db.commit()
    await db.refresh(deposit)
    return _enrich(deposit)


async def _get_deposit(deposit_id: uuid.UUID, user: User, db: AsyncSession) -> Deposit:
    result = await db.execute(
        select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user.id)
    )
    deposit = result.scalar_one_or_none()
    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deposit not found")
    return deposit


@router.get("/{deposit_id}", response_model=DepositOut)
async def get_deposit(
    deposit_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deposit = await _get_deposit(deposit_id, current_user, db)
    return _enrich(deposit)


@router.put("/{deposit_id}", response_model=DepositOut)
async def update_deposit(
    deposit_id: uuid.UUID,
    body: DepositUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deposit = await _get_deposit(deposit_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(deposit, field, value)
    await db.commit()
    await db.refresh(deposit)
    return _enrich(deposit)


@router.delete("/{deposit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deposit(
    deposit_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deposit = await _get_deposit(deposit_id, current_user, db)
    await db.delete(deposit)
    await db.commit()
