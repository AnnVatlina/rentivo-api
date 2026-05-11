from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.settings import UserSettingsOut, UserSettingsUpdate
from app.services import demo as demo_svc

router = APIRouter(dependencies=[Depends(get_current_user)])


async def _get_settings(user: User, db: AsyncSession) -> UserSettings:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    return result.scalar_one()


@router.get("", response_model=UserSettingsOut)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_settings(current_user, db)


@router.put("", response_model=UserSettingsOut)
async def update_settings(
    body: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await _get_settings(current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    await db.commit()
    await db.refresh(settings)
    return settings


@router.post("/demo-data", status_code=201)
async def load_demo_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await demo_svc.seed_demo_data(current_user.id, db)


@router.delete("/data", status_code=200)
async def clear_all_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await demo_svc.clear_all_data(current_user.id, db)
