from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app.models import User, AuditLog
from app.schemas import UserCreate, UserUpdate, UserPasswordChange, UserOut
from app.core.security import hash_password
from app.core.dependencies import require_admin, get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()


@router.post("/", response_model=UserOut)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")

    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        email=data.email,
        role=data.role,
        tg_id=data.tg_id,
        tg_username=data.tg_username,
        partner_id=data.partner_id,
        avatar_color=data.avatar_color,
    )
    db.add(user)
    await db.flush()

    db.add(AuditLog(
        user_id=current_user.id,
        action="create",
        entity="user",
        entity_id=user.id,
        new_data={"username": user.username, "role": user.role},
    ))
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    old = {"role": user.role, "is_active": user.is_active}
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)

    db.add(AuditLog(
        user_id=current_user.id,
        action="update",
        entity="user",
        entity_id=user_id,
        old_data=old,
        new_data=data.model_dump(exclude_none=True),
    ))
    return user


@router.post("/{user_id}/password")
async def change_password(
    user_id: str,
    data: UserPasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.hashed_password = hash_password(data.new_password)
    db.add(AuditLog(user_id=current_user.id, action="password_change", entity="user", entity_id=user_id))
    return {"ok": True}


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
    user.is_active = False
    db.add(AuditLog(user_id=current_user.id, action="deactivate", entity="user", entity_id=user_id))
    return {"ok": True}
