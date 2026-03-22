from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import NotificationChannel, User
from app.core.dependencies import require_admin

router = APIRouter(prefix="/notification-channels", tags=["notifications"])


class ChannelCreate(BaseModel):
    name: str
    chat_id: str
    notify_income:  bool = True
    notify_expense: bool = True
    notify_inkas:   bool = True
    notify_payment: bool = True
    notify_ad:      bool = False
    notify_server:  bool = True


class ChannelUpdate(BaseModel):
    name:            Optional[str]  = None
    chat_id:         Optional[str]  = None
    is_active:       Optional[bool] = None
    notify_income:   Optional[bool] = None
    notify_expense:  Optional[bool] = None
    notify_inkas:    Optional[bool] = None
    notify_payment:  Optional[bool] = None
    notify_ad:       Optional[bool] = None
    notify_server:   Optional[bool] = None


def _ch_dict(ch: NotificationChannel) -> dict:
    return {
        "id": ch.id, "name": ch.name, "chat_id": ch.chat_id,
        "is_active": ch.is_active,
        "notify_income": ch.notify_income,
        "notify_expense": ch.notify_expense,
        "notify_inkas": ch.notify_inkas,
        "notify_payment": ch.notify_payment,
        "notify_ad": ch.notify_ad,
        "notify_server": ch.notify_server,
        "created_at": ch.created_at,
    }


@router.get("/")
async def list_channels(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(NotificationChannel).order_by(NotificationChannel.created_at)
    )
    return [_ch_dict(ch) for ch in result.scalars().all()]


@router.post("/")
async def create_channel(
    data: ChannelCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    ch = NotificationChannel(**data.model_dump())
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    return _ch_dict(ch)


@router.patch("/{ch_id}")
async def update_channel(
    ch_id: str,
    data: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(NotificationChannel).where(NotificationChannel.id == ch_id)
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Канал не найден")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(ch, k, v)
    await db.commit()
    await db.refresh(ch)
    return _ch_dict(ch)


@router.delete("/{ch_id}")
async def delete_channel(
    ch_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(NotificationChannel).where(NotificationChannel.id == ch_id)
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Канал не найден")
    await db.delete(ch)
    await db.commit()
    return {"ok": True}


@router.post("/test/{ch_id}")
async def test_channel(
    ch_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Отправляет тестовое сообщение в канал."""
    result = await db.execute(
        select(NotificationChannel).where(NotificationChannel.id == ch_id)
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Канал не найден")

    from app.services.notification_service import _send_message
    from app.models import AppSettings
    tok_r = await db.execute(
        select(AppSettings).where(AppSettings.key == "tg_bot_token")
    )
    tok = tok_r.scalar_one_or_none()
    if not tok or not tok.value:
        raise HTTPException(status_code=400, detail="Токен бота не настроен")

    ok = await _send_message(tok.value, ch.chat_id, f"✅ <b>Тест</b>\nКанал '{ch.name}' работает!")
    if not ok:
        raise HTTPException(status_code=400, detail="Не удалось отправить сообщение. Проверьте chat_id и токен.")
    return {"ok": True}
