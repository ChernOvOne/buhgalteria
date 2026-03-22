from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.database import engine, Base
from app.config import settings
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.transactions import router as transactions_router
from app.api.categories import router as categories_router
from app.api.partners import router as partners_router
from app.api.reports import router as reports_router
from app.api.settings import router as settings_router
from app.api.other import (
    servers_router, ads_router, recurring_router,
    dashboard_router, milestones_router, stats_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём таблицы при старте
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Создаём папку для загрузок
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Создаём первого администратора если нет пользователей
    from app.database import AsyncSessionLocal
    from app.models import User, UserRole
    from app.core.security import hash_password
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        count_result = await db.execute(select(func.count(User.id)))
        count = count_result.scalar()
        if count == 0:
            admin = User(
                username="admin",
                hashed_password=hash_password("admin123"),
                full_name="Администратор",
                role=UserRole.admin,
                avatar_color="#534AB7",
            )
            db.add(admin)
            await db.commit()
            print("✓ Создан администратор: admin / admin123")

    yield
    await engine.dispose()


app = FastAPI(
    title="Buhgalteria API",
    description="Система учёта финансов бизнеса",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы (чеки)
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Роутеры
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(transactions_router, prefix="/api")
app.include_router(categories_router, prefix="/api")
app.include_router(partners_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(servers_router, prefix="/api")
app.include_router(ads_router, prefix="/api")
app.include_router(recurring_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(milestones_router, prefix="/api")
app.include_router(stats_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
