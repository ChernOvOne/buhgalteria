from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel
import secrets

from app.database import get_db
from app.models import Payment, ApiKey, Transaction, TransactionType, AppSettings
from app.core.dependencies import require_admin, get_current_user

router = APIRouter(prefix="/payments", tags=["payments"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class WebhookPayload(BaseModel):
    api_key: str
    amount: float
    currency: str = "RUB"
    external_id: Optional[str] = None
    customer_email: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    plan: Optional[str] = None           # "3 месяц VPN"
    plan_tag: Optional[str] = None       # "3m"
    subscription_start: Optional[str] = None
    subscription_end: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None


class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyOut(BaseModel):
    id: str
    name: str
    key: str
    is_active: bool
    request_count: int
    last_used: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Webhook endpoint ──────────────────────────────────────────────────────────

@router.post("/webhook")
async def receive_payment(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    # Проверяем API-ключ
    key_result = await db.execute(
        select(ApiKey).where(ApiKey.key == payload.api_key, ApiKey.is_active == True)
    )
    api_key = key_result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=401, detail="Неверный API ключ")

    # Обновляем статистику ключа
    api_key.last_used = datetime.utcnow()
    api_key.request_count = (api_key.request_count or 0) + 1

    # Проверяем дублирование по external_id
    if payload.external_id:
        dup = await db.execute(
            select(Payment).where(Payment.external_id == payload.external_id)
        )
        if dup.scalar_one_or_none():
            return {"ok": True, "status": "duplicate", "message": "Платёж уже обработан"}

    today_date = date.today()

    # Создаём транзакцию дохода
    transaction = Transaction(
        type=TransactionType.income,
        amount=payload.amount,
        date=today_date,
        description=payload.description or payload.plan or "Платёж через API",
    )
    db.add(transaction)
    await db.flush()

    # Парсим даты подписки
    sub_start = None
    sub_end = None
    if payload.subscription_start:
        try:
            sub_start = date.fromisoformat(payload.subscription_start)
        except ValueError:
            pass
    if payload.subscription_end:
        try:
            sub_end = date.fromisoformat(payload.subscription_end)
        except ValueError:
            pass

    # Создаём запись платежа
    payment = Payment(
        external_id=payload.external_id,
        api_key_id=api_key.id,
        amount=payload.amount,
        currency=payload.currency,
        customer_email=payload.customer_email,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        plan=payload.plan,
        plan_tag=payload.plan_tag,
        sub_start=sub_start,
        sub_end=sub_end,
        description=payload.description,
        source=payload.source or api_key.name,
        raw_data=payload.model_dump(),
        transaction_id=transaction.id,
        date=today_date,
    )
    db.add(payment)
    await db.flush()

    # Ищем UTM-лида по customer_id и связываем
    if payload.customer_id:
        try:
            from app.models import UtmLead
            lead_r = await db.execute(
                select(UtmLead)
                .where(UtmLead.customer_id == payload.customer_id)
                .order_by(UtmLead.created_at.desc())
                .limit(1)
            )
            lead = lead_r.scalar_one_or_none()
            if lead and not lead.converted:
                lead.converted = True
                payment.utm_code = lead.utm_code
        except Exception:
            pass

    # Создаём/обновляем Customer
    if payload.customer_id:
        try:
            from app.api.customers import get_or_create_customer, update_customer_on_payment
            await get_or_create_customer(
                db,
                telegram_id=payload.customer_id,
                telegram_username=None,
                full_name=payload.customer_name,
            )
            await update_customer_on_payment(
                db,
                telegram_id=payload.customer_id,
                amount=payload.amount,
                plan=payload.plan,
                plan_tag=payload.plan_tag,
                sub_start=sub_start,
                sub_end=sub_end,
            )
        except Exception:
            pass

    await db.commit()

    # Уведомление
    try:
        from app.services.notification_service import notify, format_payment
        from app.models import AppSettings
        from sqlalchemy import select as _select
        company_r = await db.execute(_select(AppSettings).where(AppSettings.key == "company_name"))
        company_row = company_r.scalar_one_or_none()
        company = company_row.value if company_row else "Бухгалтерия"
        text = format_payment(
            amount=payload.amount,
            plan=payload.plan,
            customer=payload.customer_name or payload.customer_email or payload.customer_id,
            source=payload.source or api_key.name,
            company=company,
        )
        import asyncio as _asyncio
        _asyncio.ensure_future(notify(db, "payment", text))
    except Exception:
        pass

    return {
        "ok": True,
        "status": "created",
        "payment_id": payment.id,
        "transaction_id": transaction.id,
    }


# ── Payment list ──────────────────────────────────────────────────────────────

@router.get("/")
async def list_payments(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    plan_tag: Optional[str] = None,
    search: Optional[str] = None,
    subscription_status: Optional[str] = None,  # active|expired|expiring_soon|no_sub
    expiring_days: int = 3,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _ = Depends(get_current_user),
):
    from datetime import timedelta as _td
    q = select(Payment)
    filters = []
    if date_from:
        filters.append(Payment.date >= date_from)
    if date_to:
        filters.append(Payment.date <= date_to)
    if plan_tag:
        filters.append(Payment.plan_tag == plan_tag)
    if subscription_status:
        _today = date.today()
        if subscription_status == "active":
            filters.append(Payment.sub_end >= _today)
        elif subscription_status == "expired":
            filters.append(Payment.sub_end < _today)
        elif subscription_status == "expiring_soon":
            filters.append(Payment.sub_end >= _today)
            filters.append(Payment.sub_end <= _today + _td(days=expiring_days))
        elif subscription_status == "no_sub":
            filters.append(Payment.sub_end == None)
    if search:
        filters.append(
            Payment.customer_email.ilike(f"%{search}%") |
            Payment.customer_name.ilike(f"%{search}%") |
            Payment.customer_id.ilike(f"%{search}%")
        )
    if filters:
        q = q.where(and_(*filters))
    q = q.order_by(Payment.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    payments = result.scalars().all()
    return [_payment_dict(p) for p in payments]


def _payment_dict(p: Payment) -> dict:
    return {
        "id": p.id,
        "external_id": p.external_id,
        "amount": p.amount,
        "currency": p.currency,
        "customer_email": p.customer_email,
        "customer_id": p.customer_id,
        "customer_name": p.customer_name,
        "plan": p.plan,
        "plan_tag": p.plan_tag,
        "sub_start": str(p.sub_start) if p.sub_start else None,
        "sub_end": str(p.sub_end) if p.sub_end else None,
        "description": p.description,
        "source": p.source,
        "utm_code": p.utm_code,
        "date": str(p.date),
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/{payment_id}")
async def get_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(get_current_user),
):
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    d = _payment_dict(p)
    d["raw_data"] = p.raw_data
    return d


@router.delete("/{payment_id}")
async def delete_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_admin),
):
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    # Удаляем и связанную транзакцию
    if p.transaction_id:
        tr = await db.execute(select(Transaction).where(Transaction.id == p.transaction_id))
        t = tr.scalar_one_or_none()
        if t:
            await db.delete(t)
    await db.delete(p)
    await db.commit()
    return {"ok": True}


# ── Statistics ────────────────────────────────────────────────────────────────

@router.get("/stats/summary")
async def payment_stats(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    _ = Depends(get_current_user),
):
    today_date = date.today()
    if not date_from:
        date_from = today_date.replace(day=1)
    if not date_to:
        date_to = today_date

    q_base = and_(Payment.date >= date_from, Payment.date <= date_to)

    # Общая сумма и кол-во
    total_r = await db.execute(
        select(func.sum(Payment.amount), func.count(Payment.id)).where(q_base)
    )
    total_amount, total_count = total_r.one()

    # По тарифам
    plans_r = await db.execute(
        select(Payment.plan_tag, Payment.plan, func.count(Payment.id), func.sum(Payment.amount))
        .where(q_base)
        .group_by(Payment.plan_tag, Payment.plan)
        .order_by(func.count(Payment.id).desc())
    )
    plans = [
        {"tag": r[0], "plan": r[1], "count": r[2], "amount": float(r[3] or 0)}
        for r in plans_r.all()
    ]

    # Истекающие подписки через 3 дня
    from datetime import timedelta
    expiry_soon_r = await db.execute(
        select(func.count(Payment.id))
        .where(
            and_(
                Payment.sub_end >= today_date,
                Payment.sub_end <= today_date + timedelta(days=3),
            )
        )
    )
    expiring_soon = expiry_soon_r.scalar() or 0

    # Активные подписки (sub_end >= today)
    active_r = await db.execute(
        select(func.count(Payment.id))
        .where(Payment.sub_end >= today_date)
    )
    active_subs = active_r.scalar() or 0

    # Сегодня
    today_r = await db.execute(
        select(func.sum(Payment.amount), func.count(Payment.id))
        .where(Payment.date == today_date)
    )
    today_amount, today_count = today_r.one()

    return {
        "total_amount": float(total_amount or 0),
        "total_count": total_count or 0,
        "today_amount": float(today_amount or 0),
        "today_count": today_count or 0,
        "active_subscriptions": active_subs,
        "expiring_soon": expiring_soon,
        "plans": plans,
        "period": {"from": str(date_from), "to": str(date_to)},
    }


# ── API Keys ──────────────────────────────────────────────────────────────────

@router.get("/keys/list", response_model=List[ApiKeyOut])
async def list_keys(
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_admin),
):
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return result.scalars().all()


@router.post("/keys", response_model=ApiKeyOut)
async def create_key(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_admin),
):
    key = ApiKey(
        name=data.name,
        key=secrets.token_urlsafe(32),
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key


@router.delete("/keys/{key_id}")
async def delete_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_admin),
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Ключ не найден")
    key.is_active = False
    await db.commit()
    return {"ok": True}
