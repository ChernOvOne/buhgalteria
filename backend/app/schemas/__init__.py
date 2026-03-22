from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import date, datetime
from app.models import UserRole, TransactionType, InkasType, ServerStatus


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: UserRole = UserRole.editor
    tg_id: Optional[str] = None
    tg_username: Optional[str] = None
    partner_id: Optional[str] = None
    avatar_color: Optional[str] = "#534AB7"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    tg_id: Optional[str] = None
    tg_username: Optional[str] = None
    partner_id: Optional[str] = None
    avatar_color: Optional[str] = None
    is_active: Optional[bool] = None


class UserPasswordChange(BaseModel):
    new_password: str


class UserOut(BaseModel):
    id: str
    username: str
    full_name: Optional[str]
    email: Optional[str]
    role: UserRole
    tg_username: Optional[str]
    avatar_color: Optional[str]
    partner_id: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Category ──────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    color: str = "#534AB7"
    icon: Optional[str] = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryOut(BaseModel):
    id: str
    name: str
    color: str
    icon: Optional[str]
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True


class AutoTagRuleCreate(BaseModel):
    category_id: str
    keyword: str


class AutoTagRuleOut(BaseModel):
    id: str
    category_id: str
    keyword: str

    class Config:
        from_attributes = True


# ── Transaction ───────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    type: TransactionType
    amount: float
    date: date
    category_id: Optional[str] = None
    description: Optional[str] = None
    receipt_url: Optional[str] = None
    is_historical: bool = False


class TransactionUpdate(BaseModel):
    amount: Optional[float] = None
    date: Optional[date] = None
    category_id: Optional[str] = None
    description: Optional[str] = None
    receipt_url: Optional[str] = None


class TransactionOut(BaseModel):
    id: str
    type: TransactionType
    amount: float
    date: date
    category_id: Optional[str]
    category: Optional[CategoryOut]
    description: Optional[str]
    receipt_url: Optional[str]
    receipt_file: Optional[str]
    is_historical: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Partner ───────────────────────────────────────────────────────────────────

class PartnerCreate(BaseModel):
    name: str
    role_label: str = "Партнёр"
    tg_username: Optional[str] = None
    tg_id: Optional[str] = None
    share_percent: Optional[float] = None
    avatar_color: str = "#534AB7"
    initials: Optional[str] = None
    notes: Optional[str] = None
    initial_investment: float = 0.0
    initial_returned: float = 0.0
    initial_dividends: float = 0.0


class PartnerUpdate(BaseModel):
    name: Optional[str] = None
    role_label: Optional[str] = None
    tg_username: Optional[str] = None
    tg_id: Optional[str] = None
    share_percent: Optional[float] = None
    avatar_color: Optional[str] = None
    initials: Optional[str] = None
    notes: Optional[str] = None
    initial_investment: Optional[float] = None
    initial_returned: Optional[float] = None
    initial_dividends: Optional[float] = None
    is_active: Optional[bool] = None


class InkasRecordCreate(BaseModel):
    partner_id: str
    type: InkasType
    amount: float
    date: date
    month_label: Optional[str] = None
    description: Optional[str] = None


class InkasRecordOut(BaseModel):
    id: str
    partner_id: str
    type: InkasType
    amount: float
    date: date
    month_label: Optional[str]
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PartnerStats(BaseModel):
    total_invested: float
    total_returned: float
    remaining_debt: float
    total_dividends: float
    avg_dividend: float
    last_dividend_amount: Optional[float]
    last_dividend_date: Optional[date]
    forecast_next: Optional[float]
    records: List[InkasRecordOut]


class PartnerOut(BaseModel):
    id: str
    name: str
    role_label: str
    tg_username: Optional[str]
    tg_id: Optional[str]
    share_percent: Optional[float]
    avatar_color: str
    initials: Optional[str]
    notes: Optional[str]
    initial_investment: float
    initial_returned: float
    initial_dividends: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PartnerDetail(PartnerOut):
    stats: PartnerStats


# ── Server ────────────────────────────────────────────────────────────────────

class ServerCreate(BaseModel):
    name: str
    provider: Optional[str] = None
    ip_address: Optional[str] = None
    purpose: Optional[str] = None
    panel_url: Optional[str] = None
    monthly_cost: Optional[float] = None
    currency: str = "RUB"
    payment_day: Optional[int] = None
    next_payment_date: Optional[date] = None
    notify_days_before: int = 5
    notes: Optional[str] = None


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    ip_address: Optional[str] = None
    purpose: Optional[str] = None
    panel_url: Optional[str] = None
    monthly_cost: Optional[float] = None
    payment_day: Optional[int] = None
    next_payment_date: Optional[date] = None
    status: Optional[ServerStatus] = None
    notify_days_before: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ServerOut(BaseModel):
    id: str
    name: str
    provider: Optional[str]
    ip_address: Optional[str]
    purpose: Optional[str]
    panel_url: Optional[str]
    monthly_cost: Optional[float]
    currency: str
    payment_day: Optional[int]
    next_payment_date: Optional[date]
    status: ServerStatus
    notify_days_before: int
    is_active: bool
    notes: Optional[str]
    days_until_payment: Optional[int] = None

    class Config:
        from_attributes = True


# ── Ad Campaign ───────────────────────────────────────────────────────────────

class AdCampaignCreate(BaseModel):
    date: date
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None
    format: Optional[str] = None
    amount: float
    subscribers_gained: Optional[int] = None
    screenshot_url: Optional[str] = None
    notes: Optional[str] = None
    budget_source: Optional[str] = "account"       # account | investment | stats_only
    investor_partner_id: Optional[str] = None


class AdCampaignUpdate(BaseModel):
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None
    format: Optional[str] = None
    amount: Optional[float] = None
    subscribers_gained: Optional[int] = None
    screenshot_url: Optional[str] = None
    notes: Optional[str] = None
    budget_source: Optional[str] = None
    investor_partner_id: Optional[str] = None


class AdCampaignOut(BaseModel):
    id: str
    date: date
    channel_name: Optional[str]
    channel_url: Optional[str]
    format: Optional[str]
    amount: float
    subscribers_gained: Optional[int]
    screenshot_url: Optional[str]
    cost_per_sub: Optional[float] = None
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Recurring Payment ─────────────────────────────────────────────────────────

class RecurringPaymentCreate(BaseModel):
    name: str
    category_id: Optional[str] = None
    amount: float
    currency: str = "RUB"
    payment_day: int
    description: Optional[str] = None
    server_id: Optional[str] = None


class RecurringPaymentOut(BaseModel):
    id: str
    name: str
    category_id: Optional[str]
    category: Optional[CategoryOut]
    amount: float
    currency: str
    payment_day: int
    description: Optional[str]
    is_active: bool
    days_until: Optional[int] = None

    class Config:
        from_attributes = True


# ── Monthly Stats ─────────────────────────────────────────────────────────────

class MonthlyStatsUpdate(BaseModel):
    online_count: Optional[int] = None
    online_weekly: Optional[int] = None
    pdp_in_channel: Optional[int] = None
    avg_check: Optional[float] = None
    total_payments: Optional[int] = None
    total_refunds: Optional[float] = None
    tag_paid: Optional[int] = None
    notes: Optional[str] = None


class MonthlyStatsOut(BaseModel):
    id: str
    year: int
    month: int
    online_count: Optional[int]
    online_weekly: Optional[int]
    pdp_in_channel: Optional[int]
    avg_check: Optional[float]
    total_payments: Optional[int]
    total_refunds: Optional[float]
    tag_paid: Optional[int]
    notes: Optional[str]

    class Config:
        from_attributes = True


# ── Dashboard ─────────────────────────────────────────────────────────────────

class PeriodKPI(BaseModel):
    income: float
    expense: float
    profit: float
    avg_per_day: float
    best_day: Optional[date]
    best_day_amount: Optional[float]


class DashboardData(BaseModel):
    today: PeriodKPI
    month: PeriodKPI
    year: PeriodKPI
    balance: float
    expense_by_category: List[dict]
    income_chart: List[dict]       # [{date, amount}]
    partners_summary: List[dict]
    servers_warning: List[ServerOut]
    ad_stats: dict
    recent_transactions: List[TransactionOut]
    milestones: List[dict]


# ── Milestone ─────────────────────────────────────────────────────────────────

class MilestoneCreate(BaseModel):
    title: str
    target_amount: float
    type: str = "revenue"


class MilestoneOut(BaseModel):
    id: str
    title: str
    target_amount: float
    current_amount: float
    type: str
    is_completed: bool
    progress_percent: float = 0.0

    class Config:
        from_attributes = True


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    balance: Optional[float] = None
    tg_bot_token: Optional[str] = None
    tg_channel_id: Optional[str] = None
    tg_admin_id: Optional[str] = None
    notify_income: Optional[bool] = None
    notify_expense: Optional[bool] = None
    notify_daily: Optional[bool] = None
    notify_monthly: Optional[bool] = None
    notify_server: Optional[bool] = None
    notify_anomaly: Optional[bool] = None
    tg_allowed_ids: Optional[str] = None   # "123456,789012" — белый список TG ID


# ── Report ────────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    date_from: date
    date_to: date
    format: str = "pdf"   # pdf | excel | csv


# ── Onboarding ────────────────────────────────────────────────────────────────

class OnboardingData(BaseModel):
    company_name: str
    currency: str = "RUB"
    timezone: str = "Europe/Moscow"
    starting_balance: float = 0.0
    historical_income: float = 0.0
    historical_expense: float = 0.0
    total_investments: float = 0.0
    total_returned: float = 0.0
    total_dividends: float = 0.0
    accounting_start_month: Optional[str] = None
    categories: List[CategoryCreate] = []
    partners: List[PartnerCreate] = []
    tg_bot_token: Optional[str] = None
    tg_channel_id: Optional[str] = None
    tg_admin_id: Optional[str] = None


TokenResponse.model_rebuild()
