from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.core.security import verify_password, create_access_token
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == data.username, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import AppSettings
    result = await db.execute(
        select(AppSettings).where(AppSettings.key == "onboarding_done")
    )
    row = result.scalar_one_or_none()
    onboarding_done = row.value == "1" if row else False
    user_data = UserOut.model_validate(current_user).model_dump()
    user_data["onboarding_done"] = onboarding_done
    return user_data


@router.post("/logout")
async def logout():
    return {"ok": True}
