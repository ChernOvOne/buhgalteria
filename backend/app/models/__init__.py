from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Enum as SAEnum, JSON, Date
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum
import uuid


def gen_uuid():
    return str(uuid.uuid4())


# ── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin = "admin"
    editor = "editor"
    investor = "investor"
    partner = "partner"


class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"


class InkasType(str, enum.Enum):
    dividend = "dividend"       # ДВД
    return_inv = "return_inv"   # ВОЗВРИНВ
    investment = "investment"   # вложение


class ServerStatus(str, enum.Enum):
    active = "active"
    warning = "warning"   # скоро оплата
    expired = "expired"
    inactive = "inactive"


# ── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=True)
    hashed_password = Column(String(256), nullable=False)
    full_name = Column(String(128), nullable=True)
    role = Column(SAEnum(UserRole, create_type=False), default=UserRole.editor, nullable=False)
    tg_id = Column(String(32), nullable=True)
    tg_username = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True)
    avatar_color = Column(String(16), default="#534AB7")
    partner_id = Column(String, ForeignKey("partners.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    partner = relationship("Partner", back_populates="user", foreign_keys=[partner_id])
    audit_logs = relationship("AuditLog", back_populates="user")


# ── Category ─────────────────────────────────────────────────────────────────

class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(64), nullable=False)
    color = Column(String(16), default="#534AB7")
    icon = Column(String(32), nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transactions = relationship("Transaction", back_populates="category")
    auto_rules = relationship("AutoTagRule", back_populates="category")


class AutoTagRule(Base):
    """Правила автоматической классификации расходов"""
    __tablename__ = "auto_tag_rules"

    id = Column(String, primary_key=True, default=gen_uuid)
    category_id = Column(String, ForeignKey("categories.id"), nullable=False)
    keyword = Column(String(64), nullable=False)  # 'fornex', 'procloud', 'фнс'

    category = relationship("Category", back_populates="auto_rules")


# ── Transaction ───────────────────────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=gen_uuid)
    type = Column(SAEnum(TransactionType, create_type=False), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False, index=True)
    category_id = Column(String, ForeignKey("categories.id"), nullable=True)
    description = Column(Text, nullable=True)
    receipt_url = Column(Text, nullable=True)   # ссылка на чек (Яндекс.Диск / файл)
    receipt_file = Column(String, nullable=True) # локальный файл
    is_historical = Column(Boolean, default=False)  # исторические данные из Excel
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category = relationship("Category", back_populates="transactions")
    creator = relationship("User", foreign_keys=[created_by])


# ── Partner ───────────────────────────────────────────────────────────────────

class Partner(Base):
    __tablename__ = "partners"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(64), nullable=False)
    role_label = Column(String(32), default="Партнёр")  # "Инвестор", "Партнёр"
    tg_username = Column(String(64), nullable=True)
    tg_id = Column(String(32), nullable=True)
    share_percent = Column(Float, nullable=True)  # доля % в бизнесе
    avatar_color = Column(String(16), default="#534AB7")
    initials = Column(String(4), nullable=True)
    notes = Column(Text, nullable=True)  # заметки (только для админа)
    is_active = Column(Boolean, default=True)

    # Начальные данные (ввод при онбординге)
    initial_investment = Column(Float, default=0.0)   # вложено всего
    initial_returned = Column(Float, default=0.0)     # возвращено (до начала учёта в системе)
    initial_dividends = Column(Float, default=0.0)    # выплачено ДВД (до начала учёта)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    inkas_records = relationship("InkasRecord", back_populates="partner")
    user = relationship("User", back_populates="partner", foreign_keys="User.partner_id")


class InkasRecord(Base):
    """Инкассация: дивиденды и возврат инвестиций партнёрам"""
    __tablename__ = "inkas_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    partner_id = Column(String, ForeignKey("partners.id"), nullable=False)
    type = Column(SAEnum(InkasType, create_type=False), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    month_label = Column(String(32), nullable=True)  # "МАРТ 2026"
    description = Column(Text, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    partner = relationship("Partner", back_populates="inkas_records")
    creator = relationship("User", foreign_keys=[created_by])


# ── Server ────────────────────────────────────────────────────────────────────

class Server(Base):
    __tablename__ = "servers"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(64), nullable=False)        # "ProCloud"
    provider = Column(String(64), nullable=True)      # название провайдера
    ip_address = Column(String(64), nullable=True)
    purpose = Column(String(128), nullable=True)      # "Обход РФ + Польша"
    panel_url = Column(Text, nullable=True)           # ссылка на панель управления
    monthly_cost = Column(Float, nullable=True)
    currency = Column(String(8), default="RUB")
    payment_day = Column(Integer, nullable=True)      # число месяца
    next_payment_date = Column(Date, nullable=True)
    status = Column(SAEnum(ServerStatus, create_type=False), default=ServerStatus.active)
    notify_days_before = Column(Integer, default=5)   # за сколько дней уведомлять
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ── Ad Campaign ───────────────────────────────────────────────────────────────

class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id = Column(String, primary_key=True, default=gen_uuid)
    date = Column(Date, nullable=False)
    channel_name = Column(String(128), nullable=True)   # "Скачать тик ток мод | Redbic"
    channel_url = Column(Text, nullable=True)            # https://t.me/redbictt1
    format = Column(String(64), nullable=True)           # "2/48", "1/24", "24/24"
    amount = Column(Float, nullable=False)
    subscribers_gained = Column(Integer, nullable=True)  # приход ПДП
    screenshot_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    creator = relationship("User", foreign_keys=[created_by])


# ── Recurring Payment ─────────────────────────────────────────────────────────

class RecurringPayment(Base):
    __tablename__ = "recurring_payments"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(128), nullable=False)       # "Fornex"
    category_id = Column(String, ForeignKey("categories.id"), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(8), default="RUB")
    payment_day = Column(Integer, nullable=False)    # число месяца (1-31)
    description = Column(Text, nullable=True)        # "Нидерланды · Обход"
    server_id = Column(String, ForeignKey("servers.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("Category")
    server = relationship("Server")


# ── Monthly Stats ─────────────────────────────────────────────────────────────

class MonthlyStats(Base):
    """Ручная статистика (онлайн, ПДП) — то что нельзя посчитать автоматически"""
    __tablename__ = "monthly_stats"

    id = Column(String, primary_key=True, default=gen_uuid)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)           # 1-12
    online_count = Column(Integer, nullable=True)     # онлайн в канале
    online_weekly = Column(Integer, nullable=True)    # онлайн за неделю
    pdp_in_channel = Column(Integer, nullable=True)   # ПДП в канале
    avg_check = Column(Float, nullable=True)          # средний чек
    total_payments = Column(Integer, nullable=True)   # кол-во оплат
    total_refunds = Column(Float, nullable=True)      # сумма возвратов
    tag_paid = Column(Integer, nullable=True)         # тэг оплачено
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ── Settings ──────────────────────────────────────────────────────────────────

class AppSettings(Base):
    """Глобальные настройки приложения"""
    __tablename__ = "app_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ── Milestone ─────────────────────────────────────────────────────────────────

class Milestone(Base):
    """Цели / вехи бизнеса"""
    __tablename__ = "milestones"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String(128), nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    type = Column(String(32), default="revenue")  # revenue, profit, investment_return
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLog(Base):
    """Журнал всех действий пользователей"""
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String(64), nullable=False)   # create, update, delete
    entity = Column(String(64), nullable=False)   # transaction, partner, etc.
    entity_id = Column(String, nullable=True)
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="audit_logs")


# ── Payment (входящие платежи через webhook) ──────────────────────────────────

class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=gen_uuid)
    # Идентификация
    external_id = Column(String(128), nullable=True, index=True)   # ID из вашей системы
    api_key_id  = Column(String, ForeignKey("api_keys.id"), nullable=True)

    # Финансы
    amount   = Column(Float, nullable=False)
    currency = Column(String(8), default="RUB")

    # Клиент
    customer_email = Column(String(128), nullable=True)
    customer_id    = Column(String(128), nullable=True)
    customer_name  = Column(String(128), nullable=True)

    # Подписка VPN
    plan          = Column(String(64), nullable=True)   # "3 месяц VPN"
    plan_tag      = Column(String(32), nullable=True)   # "3m"
    sub_start     = Column(Date, nullable=True)
    sub_end       = Column(Date, nullable=True)

    # Мета
    description = Column(Text, nullable=True)
    raw_data    = Column(JSON, nullable=True)      # оригинальный JSON запроса
    source      = Column(String(64), nullable=True) # имя источника / бота

    # Автоматически создаётся транзакция дохода
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=True)

    date       = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    api_key     = relationship("ApiKey",     foreign_keys=[api_key_id])
    transaction = relationship("Transaction", foreign_keys=[transaction_id])


class ApiKey(Base):
    __tablename__ = "api_keys"

    id          = Column(String, primary_key=True, default=gen_uuid)
    name        = Column(String(64), nullable=False)   # "Бот VPN 1"
    key         = Column(String(64), unique=True, nullable=False)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    last_used   = Column(DateTime(timezone=True), nullable=True)
    request_count = Column(Integer, default=0)
