from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "Buhgalteria"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://buh:buhpass@db:5432/buhdb"
    DATABASE_URL_SYNC: str = "postgresql://buh:buhpass@db:5432/buhdb"

    SECRET_KEY: str = "change-me-in-production-very-long-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 дней

    REDIS_URL: str = "redis://redis:6379/0"

    TG_BOT_TOKEN: Optional[str] = None
    TG_CHANNEL_ID: Optional[str] = None
    TG_ADMIN_ID: Optional[str] = None

    CURRENCY: str = "₽"
    TIMEZONE: str = "Europe/Moscow"
    COMPANY_NAME: str = "Мой бизнес"

    UPLOAD_DIR: str = "/app/uploads"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
