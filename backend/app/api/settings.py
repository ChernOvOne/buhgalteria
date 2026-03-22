from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import AppSettings, AuditLog, Category, Partner, User, Milestone
from app.schemas import SettingsUpdate, OnboardingData, CategoryCreate, PartnerCreate
from app.core.dependencies import require_admin
from app.core.security import hash_password

router = APIRouter(prefix="/settings", tags=["settings"])


async def get_setting(db: AsyncSession, key: str, default=None):
    result = await db.execute(select(AppSettings).where(AppSettings.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else default


async def set_setting(db: AsyncSession, key: str, value: str):
    result = await db.execute(select(AppSettings).where(AppSettings.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(AppSettings(key=key, value=value))


@router.get("/")
async def get_all_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(AppSettings))
    rows = result.scalars().all()
    settings = {r.key: r.value for r in rows}
    # Скрываем токен бота
    if "tg_bot_token" in settings:
        token = settings["tg_bot_token"]
        settings["tg_bot_token"] = token[:10] + "..." if token and len(token) > 10 else token
    return settings


@router.patch("/")
async def update_settings(
    data: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        await set_setting(db, key, str(value))

    db.add(AuditLog(
        user_id=current_user.id,
        action="update",
        entity="settings",
        new_data=list(updates.keys()),
    ))
    return {"ok": True}


@router.post("/onboarding")
async def complete_onboarding(
    data: OnboardingData,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Первоначальная настройка — вызывается один раз при запуске"""

    # Сохраняем базовые настройки
    await set_setting(db, "company_name", data.company_name)
    await set_setting(db, "currency", data.currency)
    await set_setting(db, "timezone", data.timezone)
    await set_setting(db, "starting_balance", str(data.starting_balance))
    await set_setting(db, "historical_income", str(data.historical_income))
    await set_setting(db, "historical_expense", str(data.historical_expense))
    await set_setting(db, "accounting_start_month", data.accounting_start_month or "")
    await set_setting(db, "onboarding_done", "1")

    if data.tg_bot_token:
        await set_setting(db, "tg_bot_token", data.tg_bot_token)
    if data.tg_channel_id:
        await set_setting(db, "tg_channel_id", data.tg_channel_id)
    if data.tg_admin_id:
        await set_setting(db, "tg_admin_id", data.tg_admin_id)

    # Создаём категории
    for cat_data in data.categories:
        existing = await db.execute(
            select(Category).where(Category.name == cat_data.name)
        )
        if not existing.scalar_one_or_none():
            db.add(Category(**cat_data.model_dump()))

    # Создаём партнёров
    for partner_data in data.partners:
        existing = await db.execute(
            select(Partner).where(Partner.name == partner_data.name)
        )
        if not existing.scalar_one_or_none():
            db.add(Partner(**partner_data.model_dump()))

    # Создаём стартовые цели если есть исторические данные
    if data.total_investments > 0 and data.total_returned < data.total_investments:
        remaining = data.total_investments - data.total_returned
        existing_m = await db.execute(select(Milestone).where(Milestone.type == "investment_return"))
        if not existing_m.scalar_one_or_none():
            db.add(Milestone(
                title="Погашение инвестиций",
                target_amount=data.total_investments,
                current_amount=data.total_returned,
                type="investment_return",
            ))

    await db.flush()
    return {"ok": True, "message": "Первоначальная настройка завершена"}


@router.get("/audit-log")
async def get_audit_log(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "entity": l.entity,
            "entity_id": l.entity_id,
            "old_data": l.old_data,
            "new_data": l.new_data,
            "created_at": l.created_at,
        }
        for l in logs
    ]
