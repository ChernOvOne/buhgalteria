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
from app.api.payments import router as payments_router
from app.api.notification_channels import router as notif_router
from app.api.compare import router as compare_router
from app.api.utm import router as utm_router
from app.api.other import (
    servers_router, ads_router, recurring_router,
    dashboard_router, milestones_router, stats_router,
)


from sqlalchemy import text

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # EXCEPTION WHEN duplicate_object — корректно обрабатывает уже существующие типы
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE userrole AS ENUM ('admin', 'editor', 'investor', 'partner');
            EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """))
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE transactiontype AS ENUM ('income', 'expense');
            EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """))
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE inkastype AS ENUM ('dividend', 'return_inv', 'investment');
            EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """))
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE serverstatus AS ENUM ('active', 'warning', 'expired', 'inactive');
            EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """))
        await conn.run_sync(Base.metadata.create_all)

        # Миграции — добавляем новые колонки если их нет
        for sql in [
            "ALTER TABLE ad_campaigns ADD COLUMN IF NOT EXISTS budget_source VARCHAR(32) DEFAULT 'account'",
            "ALTER TABLE ad_campaigns ADD COLUMN IF NOT EXISTS investor_partner_id VARCHAR REFERENCES partners(id)",
            "ALTER TABLE ad_campaigns ADD COLUMN IF NOT EXISTS transaction_id VARCHAR REFERENCES transactions(id)",
            "ALTER TABLE ad_campaigns ADD COLUMN IF NOT EXISTS utm_code VARCHAR(32)",
            "ALTER TABLE ad_campaigns ADD COLUMN IF NOT EXISTS target_url TEXT",
            "ALTER TABLE ad_campaigns ADD COLUMN IF NOT EXISTS target_type VARCHAR(16) DEFAULT 'bot'",
            "ALTER TABLE payments ADD COLUMN IF NOT EXISTS utm_code VARCHAR(32)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_ad_campaigns_utm_code ON ad_campaigns(utm_code) WHERE utm_code IS NOT NULL",
        ]:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass

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
app.include_router(payments_router, prefix="/api")
app.include_router(notif_router, prefix="/api")
app.include_router(compare_router, prefix="/api")
# UTM redirect — без /api prefix (чтобы ссылка была короткой: /go/code)
app.include_router(utm_router)
app.include_router(servers_router, prefix="/api")
app.include_router(ads_router, prefix="/api")
app.include_router(recurring_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(milestones_router, prefix="/api")
app.include_router(stats_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
