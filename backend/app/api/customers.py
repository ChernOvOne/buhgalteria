from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional, List
from datetime import date, datetime

from app.database import get_db
from app.models import Customer, Payment, UtmLead, AdCampaign, User
from app.schemas import CustomerOut, CustomerDetail, CustomerUpdate
from app.core.dependencies import get_current_user, require_editor

router = APIRouter(prefix="/customers", tags=["customers"])


def _customer_dict(c: Customer) -> dict:
    return {col.name: getattr(c, col.name) for col in c.__table__.columns}


@router.get("/", response_model=List[CustomerOut])
async def list_customers(
    search: Optional[str] = None,
    utm_code: Optional[str] = None,
    has_paid: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Customer).order_by(Customer.first_seen_at.desc())
    if search:
        q = q.where(
            or_(
                Customer.telegram_id.ilike(f"%{search}%"),
                Customer.telegram_username.ilike(f"%{search}%"),
                Customer.full_name.ilike(f"%{search}%"),
            )
        )
    if utm_code:
        q = q.where(Customer.utm_code == utm_code)
    if has_paid is True:
        q = q.where(Customer.payments_count > 0)
    elif has_paid is False:
        q = q.where(Customer.payments_count == 0)
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/stats")
async def customer_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Общая статистика по клиентской базе"""
    total_r = await db.execute(select(func.count(Customer.id)))
    total = total_r.scalar() or 0

    paid_r = await db.execute(
        select(func.count(Customer.id)).where(Customer.payments_count > 0)
    )
    paid = paid_r.scalar() or 0

    today_date = date.today()

    # Активные подписки
    active_r = await db.execute(
        select(func.count(Customer.id)).where(Customer.subscription_end >= today_date)
    )
    active_subs = active_r.scalar() or 0

    # Истекающие через 3 дня
    from datetime import timedelta
    expiring_r = await db.execute(
        select(func.count(Customer.id)).where(
            and_(
                Customer.subscription_end >= today_date,
                Customer.subscription_end <= today_date + timedelta(days=3),
            )
        )
    )
    expiring = expiring_r.scalar() or 0

    # Средний LTV
    ltv_r = await db.execute(
        select(func.avg(Customer.total_paid)).where(Customer.payments_count > 0)
    )
    avg_ltv = round(float(ltv_r.scalar() or 0), 2)

    # Новые за последние 7 дней
    week_ago = today_date - timedelta(days=6)
    new_r = await db.execute(
        select(func.count(Customer.id)).where(
            func.date(Customer.first_seen_at) >= week_ago
        )
    )
    new_week = new_r.scalar() or 0

    # Retention: из тех кто покупал 2+ месяца назад, сколько купили ещё
    two_months_ago = today_date - timedelta(days=60)
    old_paid_r = await db.execute(
        select(func.count(Customer.id)).where(
            and_(
                Customer.payments_count > 0,
                func.date(Customer.first_seen_at) <= two_months_ago,
            )
        )
    )
    old_paid = old_paid_r.scalar() or 0
    repeat_r = await db.execute(
        select(func.count(Customer.id)).where(
            and_(
                Customer.payments_count >= 2,
                func.date(Customer.first_seen_at) <= two_months_ago,
            )
        )
    )
    repeat = repeat_r.scalar() or 0
    retention_rate = round(repeat / old_paid * 100, 1) if old_paid > 0 else 0

    return {
        "total_customers": total,
        "paid_customers": paid,
        "conversion_rate": round(paid / total * 100, 1) if total > 0 else 0,
        "active_subscriptions": active_subs,
        "expiring_soon": expiring,
        "avg_ltv": avg_ltv,
        "new_this_week": new_week,
        "retention_rate": retention_rate,
        "churn_rate": round(100 - retention_rate, 1) if old_paid > 0 else 0,
    }


@router.get("/{customer_id}", response_model=CustomerDetail)
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    # История платежей
    pay_r = await db.execute(
        select(Payment)
        .where(Payment.customer_id == c.telegram_id)
        .order_by(Payment.created_at.desc())
        .limit(50)
    )
    payments = [
        {
            "id": p.id, "amount": p.amount, "plan": p.plan,
            "plan_tag": p.plan_tag, "date": str(p.date),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in pay_r.scalars().all()
    ]

    # Название кампании
    utm_campaign = None
    if c.utm_code:
        camp_r = await db.execute(
            select(AdCampaign).where(AdCampaign.utm_code == c.utm_code)
        )
        camp = camp_r.scalar_one_or_none()
        if camp:
            utm_campaign = camp.channel_name

    return CustomerDetail(
        **_customer_dict(c),
        payments=payments,
        utm_campaign=utm_campaign,
    )


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_editor),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(c, field, value)
    return c


async def get_or_create_customer(
    db: AsyncSession,
    telegram_id: str,
    telegram_username: str = None,
    full_name: str = None,
    utm_code: str = None,
    source: str = None,
) -> Customer:
    """Ищет клиента по telegram_id или создаёт нового."""
    result = await db.execute(
        select(Customer).where(Customer.telegram_id == telegram_id)
    )
    customer = result.scalar_one_or_none()
    if customer:
        # Обновляем данные если пришли новые
        if telegram_username and not customer.telegram_username:
            customer.telegram_username = telegram_username
        if full_name and not customer.full_name:
            customer.full_name = full_name
        customer.last_seen_at = datetime.utcnow()
        return customer

    # Генерируем реферальный код
    import secrets
    ref_code = "ref_" + secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]

    customer = Customer(
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        full_name=full_name,
        utm_code=utm_code,
        source=source or "direct",
        referral_code=ref_code,
    )
    db.add(customer)
    await db.flush()
    return customer


async def update_customer_on_payment(
    db: AsyncSession,
    telegram_id: str,
    amount: float,
    plan: str = None,
    plan_tag: str = None,
    sub_start: date = None,
    sub_end: date = None,
):
    """Обновляет агрегаты клиента при платеже."""
    result = await db.execute(
        select(Customer).where(Customer.telegram_id == telegram_id)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        return
    customer.total_paid = (customer.total_paid or 0) + amount
    customer.payments_count = (customer.payments_count or 0) + 1
    customer.last_payment_at = datetime.utcnow()
    if plan:
        customer.current_plan = plan
    if plan_tag:
        customer.current_plan_tag = plan_tag
    if sub_start:
        customer.subscription_start = sub_start
    if sub_end:
        customer.subscription_end = sub_end
