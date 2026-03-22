from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional
from datetime import date, datetime, timedelta

from app.database import get_db
from app.models import (
    Server, ServerStatus, AdCampaign, RecurringPayment,
    Transaction, TransactionType, Category, Partner, InkasRecord,
    InkasType, Milestone, MonthlyStats, User,
)
from app.schemas import (
    ServerCreate, ServerUpdate, ServerOut,
    AdCampaignCreate, AdCampaignUpdate, AdCampaignOut,
    RecurringPaymentCreate, RecurringPaymentOut,
    DashboardData, PeriodKPI,
    MilestoneCreate, MilestoneOut,
    MonthlyStatsUpdate, MonthlyStatsOut,
)
from app.core.dependencies import require_admin, require_editor, get_current_user

servers_router = APIRouter(prefix="/servers", tags=["servers"])
ads_router = APIRouter(prefix="/ads", tags=["ads"])
recurring_router = APIRouter(prefix="/recurring", tags=["recurring"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])
milestones_router = APIRouter(prefix="/milestones", tags=["milestones"])
stats_router = APIRouter(prefix="/monthly-stats", tags=["stats"])


def days_until(d: Optional[date]) -> Optional[int]:
    if not d:
        return None
    return (d - date.today()).days


def server_out(s: Server) -> dict:
    d = days_until(s.next_payment_date)
    status = s.status
    if d is not None:
        if d < 0:
            status = ServerStatus.expired
        elif d <= 5:
            status = ServerStatus.warning
        else:
            status = ServerStatus.active
    return {**{c.name: getattr(s, c.name) for c in s.__table__.columns},
            "days_until_payment": d, "status": status}


# ── Servers ───────────────────────────────────────────────────────────────────

@servers_router.get("/", response_model=List[ServerOut])
async def list_servers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Server).where(Server.is_active == True).order_by(Server.next_payment_date)
    )
    return [ServerOut.model_validate(server_out(s)) for s in result.scalars().all()]


@servers_router.post("/", response_model=ServerOut)
async def create_server(
    data: ServerCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_editor),
):
    s = Server(**data.model_dump())
    db.add(s)
    await db.flush()
    await db.refresh(s)
    return ServerOut.model_validate(server_out(s))


@servers_router.patch("/{server_id}", response_model=ServerOut)
async def update_server(
    server_id: str,
    data: ServerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_editor),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Сервер не найден")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(s, field, value)
    return ServerOut.model_validate(server_out(s))


@servers_router.delete("/{server_id}")
async def delete_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_editor),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Сервер не найден")
    s.is_active = False
    return {"ok": True}


# ── Ad Campaigns ──────────────────────────────────────────────────────────────

@ads_router.get("/", response_model=List[AdCampaignOut])
async def list_campaigns(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(AdCampaign)
    if date_from:
        q = q.where(AdCampaign.date >= date_from)
    if date_to:
        q = q.where(AdCampaign.date <= date_to)
    q = q.order_by(AdCampaign.date.desc())
    result = await db.execute(q)
    campaigns = result.scalars().all()

    out = []
    for c in campaigns:
        cps = round(c.amount / c.subscribers_gained, 2) if c.subscribers_gained and c.subscribers_gained > 0 else None
        out.append(AdCampaignOut.model_validate({
            **{col.name: getattr(c, col.name) for col in c.__table__.columns},
            "cost_per_sub": cps,
        }))
    return out


@ads_router.post("/", response_model=AdCampaignOut)
async def create_campaign(
    data: AdCampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    from app.models import Transaction, TransactionType, InkasRecord, InkasType, AppSettings, Category
    from app.services.notification_service import notify, format_ad

    transaction_id = None
    budget_source = data.budget_source or "account"

    # Списываем бюджет в зависимости от источника
    if budget_source == "account":
        # Ищем категорию "Реклама"
        cat_r = await db.execute(
            select(Category).where(Category.name.ilike("%реклам%")).limit(1)
        )
        cat = cat_r.scalar_one_or_none()
        t = Transaction(
            type=TransactionType.expense,
            amount=data.amount,
            date=data.date,
            category_id=cat.id if cat else None,
            description=f"Реклама: {data.channel_name or 'канал'}",
            created_by=current_user.id,
        )
        db.add(t)
        await db.flush()
        transaction_id = t.id

    elif budget_source == "investment" and data.investor_partner_id:
        # Записываем как инвестицию партнёра
        inkas = InkasRecord(
            partner_id=data.investor_partner_id,
            type=InkasType.investment,
            amount=data.amount,
            date=data.date,
            description=f"Инвестиция в рекламу: {data.channel_name or 'канал'}",
            created_by=current_user.id,
        )
        db.add(inkas)
        await db.flush()

    from app.api.utm import generate_utm_code
    ad_data = data.model_dump()
    ad_data["budget_source"] = budget_source
    ad_data["transaction_id"] = transaction_id
    # Автогенерация UTM кода если не передан
    if not ad_data.get("utm_code"):
        ad_data["utm_code"] = generate_utm_code()
    campaign = AdCampaign(**ad_data, created_by=current_user.id)
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)

    # Уведомление
    try:
        company_r = await db.execute(select(AppSettings).where(AppSettings.key == "company_name"))
        company_row = company_r.scalar_one_or_none()
        company = company_row.value if company_row else "Бухгалтерия"
        partner_name = None
        if data.investor_partner_id:
            from app.models import Partner as PartnerM
            pr = await db.execute(select(PartnerM).where(PartnerM.id == data.investor_partner_id))
            pm = pr.scalar_one_or_none()
            partner_name = pm.name if pm else None
        import asyncio as _asyncio
        _asyncio.ensure_future(notify(db, "ad", format_ad(
            channel_name=data.channel_name or "канал",
            amount=data.amount,
            budget_source=budget_source,
            partner_name=partner_name,
            user_name=current_user.full_name or current_user.username,
            company=company,
        )))
    except Exception:
        pass

    cps = round(campaign.amount / campaign.subscribers_gained, 2) if campaign.subscribers_gained and campaign.subscribers_gained > 0 else None
    return AdCampaignOut.model_validate({
        "id": campaign.id, "date": campaign.date,
        "channel_name": campaign.channel_name, "channel_url": campaign.channel_url,
        "format": campaign.format, "amount": campaign.amount,
        "subscribers_gained": campaign.subscribers_gained,
        "screenshot_url": campaign.screenshot_url, "notes": campaign.notes,
        "budget_source": campaign.budget_source,
        "investor_partner_id": campaign.investor_partner_id,
        "transaction_id": campaign.transaction_id,
        "utm_code": campaign.utm_code,
        "target_url": campaign.target_url,
        "target_type": campaign.target_type,
        "created_at": campaign.created_at,
        "cost_per_sub": cps,
    })


@ads_router.patch("/{ad_id}", response_model=AdCampaignOut)
async def update_campaign(
    ad_id: str,
    data: AdCampaignUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_editor),
):
    result = await db.execute(select(AdCampaign).where(AdCampaign.id == ad_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(c, field, value)
    cps = round(c.amount / c.subscribers_gained, 2) if c.subscribers_gained and c.subscribers_gained > 0 else None
    return AdCampaignOut.model_validate({
        **{col.name: getattr(c, col.name) for col in c.__table__.columns},
        "cost_per_sub": cps,
    })


@ads_router.delete("/{ad_id}")
async def delete_campaign(
    ad_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_editor),
):
    result = await db.execute(select(AdCampaign).where(AdCampaign.id == ad_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    await db.delete(c)
    return {"ok": True}


@ads_router.get("/summary")
async def ads_summary(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(AdCampaign)
    if date_from:
        q = q.where(AdCampaign.date >= date_from)
    if date_to:
        q = q.where(AdCampaign.date <= date_to)
    result = await db.execute(q)
    campaigns = result.scalars().all()

    total_spent = sum(c.amount for c in campaigns)
    total_subs = sum(c.subscribers_gained or 0 for c in campaigns)
    cost_per_sub = round(total_spent / total_subs, 2) if total_subs > 0 else None

    # Лучший канал по ПДП
    best = max(campaigns, key=lambda c: c.subscribers_gained or 0, default=None)

    return {
        "total_spent": total_spent,
        "total_subscribers": total_subs,
        "cost_per_sub": cost_per_sub,
        "campaigns_count": len(campaigns),
        "best_channel": {
            "name": best.channel_name,
            "url": best.channel_url,
            "subscribers": best.subscribers_gained,
            "amount": best.amount,
        } if best else None,
    }


# ── Recurring Payments ────────────────────────────────────────────────────────

@recurring_router.get("/", response_model=List[RecurringPaymentOut])
async def list_recurring(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RecurringPayment).where(RecurringPayment.is_active == True)
        .order_by(RecurringPayment.payment_day)
    )
    payments = result.scalars().all()
    today = date.today()
    out = []
    for p in payments:
        d = p.payment_day - today.day
        if d < 0:
            d += 30  # следующий месяц
        out.append(RecurringPaymentOut.model_validate({
            **{col.name: getattr(p, col.name) for col in p.__table__.columns},
            "category": None, "days_until": d,
        }))
    return out


@recurring_router.post("/", response_model=RecurringPaymentOut)
async def create_recurring(
    data: RecurringPaymentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_editor),
):
    p = RecurringPayment(**data.model_dump())
    db.add(p)
    await db.flush()
    await db.refresh(p)
    return RecurringPaymentOut.model_validate({
        **{col.name: getattr(p, col.name) for col in p.__table__.columns},
        "category": None, "days_until": None,
    })


@recurring_router.delete("/{pay_id}")
async def delete_recurring(
    pay_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_editor),
):
    result = await db.execute(select(RecurringPayment).where(RecurringPayment.id == pay_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    p.is_active = False
    return {"ok": True}


# ── Dashboard ─────────────────────────────────────────────────────────────────

async def get_period_kpi(db: AsyncSession, date_from: date, date_to: date) -> PeriodKPI:
    result = await db.execute(
        select(Transaction.type, func.sum(Transaction.amount), Transaction.date)
        .where(and_(Transaction.date >= date_from, Transaction.date <= date_to))
        .group_by(Transaction.type, Transaction.date)
    )
    rows = result.all()

    income = sum(r[1] for r in rows if r[0] == TransactionType.income)
    expense = sum(r[1] for r in rows if r[0] == TransactionType.expense)
    profit = income - expense

    days = (date_to - date_from).days + 1
    avg_per_day = income / days if days > 0 else 0

    # Лучший день
    daily = {}
    for r in rows:
        if r[0] == TransactionType.income:
            d = r[2]
            daily[d] = daily.get(d, 0) + float(r[1])

    best_day = max(daily, key=daily.get) if daily else None
    best_amount = daily[best_day] if best_day else None

    return PeriodKPI(
        income=round(income, 2),
        expense=round(expense, 2),
        profit=round(profit, 2),
        avg_per_day=round(avg_per_day, 2),
        best_day=best_day,
        best_day_amount=round(best_amount, 2) if best_amount else None,
    )


@dashboard_router.get("/")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    today_kpi = await get_period_kpi(db, today, today)
    month_kpi = await get_period_kpi(db, month_start, today)
    year_kpi = await get_period_kpi(db, year_start, today)

    # Остаток на счёте — из настроек + (доходы - расходы)
    from app.models import AppSettings
    bal_result = await db.execute(select(AppSettings).where(AppSettings.key == "starting_balance"))
    bal_row = bal_result.scalar_one_or_none()
    starting_balance = float(bal_row.value) if bal_row and bal_row.value else 0.0

    all_income_r = await db.execute(
        select(func.sum(Transaction.amount)).where(Transaction.type == TransactionType.income)
    )
    all_expense_r = await db.execute(
        select(func.sum(Transaction.amount)).where(Transaction.type == TransactionType.expense)
    )
    all_income = float(all_income_r.scalar() or 0)
    all_expense = float(all_expense_r.scalar() or 0)

    # Инкас (выплаченные деньги) тоже уменьшают баланс
    all_inkas_r = await db.execute(
        select(func.sum(InkasRecord.amount)).where(
            InkasRecord.type.in_([InkasType.dividend, InkasType.return_inv])
        )
    )
    all_inkas = float(all_inkas_r.scalar() or 0)
    balance = starting_balance + all_income - all_expense - all_inkas

    # Расходы по категориям за месяц
    cat_result = await db.execute(
        select(Category.name, Category.color, func.sum(Transaction.amount).label("total"))
        .join(Transaction, Transaction.category_id == Category.id)
        .where(
            and_(
                Transaction.type == TransactionType.expense,
                Transaction.date >= month_start,
                Transaction.date <= today,
            )
        )
        .group_by(Category.id, Category.name, Category.color)
        .order_by(func.sum(Transaction.amount).desc())
    )
    expense_by_cat = [
        {"name": r[0], "color": r[1], "amount": round(float(r[2]), 2)}
        for r in cat_result.all()
    ]

    # График дохода за последние 30 дней
    chart_from = today - timedelta(days=29)
    chart_result = await db.execute(
        select(Transaction.date, func.sum(Transaction.amount))
        .where(and_(
            Transaction.type == TransactionType.income,
            Transaction.date >= chart_from,
            Transaction.date <= today,
        ))
        .group_by(Transaction.date)
        .order_by(Transaction.date)
    )
    income_chart = [
        {"date": str(r[0]), "amount": round(float(r[1]), 2)}
        for r in chart_result.all()
    ]

    # Сводка по партнёрам
    partners_result = await db.execute(select(Partner).where(Partner.is_active == True))
    partners = partners_result.scalars().all()
    partners_summary = []
    for p in partners:
        last_dvd_r = await db.execute(
            select(InkasRecord)
            .where(and_(InkasRecord.partner_id == p.id, InkasRecord.type == InkasType.dividend))
            .order_by(InkasRecord.date.desc())
            .limit(1)
        )
        last_dvd = last_dvd_r.scalar_one_or_none()
        total_invested = p.initial_investment
        total_returned = p.initial_returned
        total_dividends = p.initial_dividends

        invest_r = await db.execute(
            select(func.sum(InkasRecord.amount))
            .where(and_(InkasRecord.partner_id == p.id, InkasRecord.type == InkasType.investment))
        )
        ret_r = await db.execute(
            select(func.sum(InkasRecord.amount))
            .where(and_(InkasRecord.partner_id == p.id, InkasRecord.type == InkasType.return_inv))
        )
        dvd_r = await db.execute(
            select(func.sum(InkasRecord.amount))
            .where(and_(InkasRecord.partner_id == p.id, InkasRecord.type == InkasType.dividend))
        )
        total_invested += float(invest_r.scalar() or 0)
        total_returned += float(ret_r.scalar() or 0)
        total_dividends += float(dvd_r.scalar() or 0)

        partners_summary.append({
            "id": p.id,
            "name": p.name,
            "role_label": p.role_label,
            "avatar_color": p.avatar_color,
            "initials": p.initials,
            "last_dividend": last_dvd.amount if last_dvd else None,
            "last_dividend_date": str(last_dvd.date) if last_dvd else None,
            "remaining_debt": max(0.0, total_invested - total_returned),
            "total_invested": total_invested,
            "total_returned": total_returned,
            "total_dividends": total_dividends,
        })

    # Серверы требующие внимания
    servers_result = await db.execute(
        select(Server).where(Server.is_active == True)
    )
    servers_warn = []
    for s in servers_result.scalars().all():
        d = days_until(s.next_payment_date)
        if d is not None and d <= 7:
            servers_warn.append(ServerOut.model_validate({
                **{col.name: getattr(s, col.name) for col in s.__table__.columns},
                "days_until_payment": d,
                "status": ServerStatus.warning if d >= 0 else ServerStatus.expired,
            }))

    # Рекламная сводка за месяц
    ads_result = await db.execute(
        select(AdCampaign).where(
            and_(AdCampaign.date >= month_start, AdCampaign.date <= today)
        )
    )
    ads = ads_result.scalars().all()
    total_ad_spend = sum(a.amount for a in ads)
    total_subs = sum(a.subscribers_gained or 0 for a in ads)
    ad_stats = {
        "total_spent": round(total_ad_spend, 2),
        "total_subscribers": total_subs,
        "cost_per_sub": round(total_ad_spend / total_subs, 2) if total_subs > 0 else None,
        "campaigns_count": len(ads),
    }

    # Последние 10 транзакций
    recent_r = await db.execute(
        select(Transaction).order_by(Transaction.date.desc(), Transaction.created_at.desc()).limit(10)
    )
    recent = [
        {
            "id": t.id, "type": t.type, "amount": t.amount, "date": t.date,
            "category_id": t.category_id, "category": None,
            "description": t.description, "receipt_url": t.receipt_url,
            "receipt_file": t.receipt_file, "is_historical": t.is_historical,
            "created_at": t.created_at,
        }
        for t in recent_r.scalars().all()
    ]

    # Milestones
    mil_r = await db.execute(select(Milestone).where(Milestone.is_completed == False))
    milestones = []
    for m in mil_r.scalars().all():
        pct = round(min(100.0, m.current_amount / m.target_amount * 100), 1) if m.target_amount > 0 else 0
        milestones.append({
            "id": m.id, "title": m.title,
            "target_amount": m.target_amount, "current_amount": m.current_amount,
            "type": m.type, "progress_percent": pct,
        })

    # Последние платежи через API
    from app.models import Payment
    pay_r = await db.execute(
        select(Payment).order_by(Payment.created_at.desc()).limit(6)
    )
    recent_payments = [
        {
            "id": p.id, "amount": p.amount, "plan": p.plan,
            "plan_tag": p.plan_tag, "customer_email": p.customer_email,
            "customer_id": p.customer_id, "date": str(p.date),
        }
        for p in pay_r.scalars().all()
    ]

    return {
        "today": today_kpi.model_dump(),
        "month": month_kpi.model_dump(),
        "year": year_kpi.model_dump(),
        "balance": round(balance, 2),
        "expense_by_category": expense_by_cat,
        "income_chart": income_chart,
        "partners_summary": partners_summary,
        "servers_warning": servers_warn,
        "ad_stats": ad_stats,
        "recent_transactions": recent,
        "recent_payments": recent_payments,
        "milestones": milestones,
    }


# ── Milestones ────────────────────────────────────────────────────────────────

@milestones_router.get("/", response_model=List[MilestoneOut])
async def list_milestones(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Milestone).order_by(Milestone.is_completed, Milestone.created_at))
    milestones = result.scalars().all()
    out = []
    for m in milestones:
        pct = round(min(100.0, m.current_amount / m.target_amount * 100), 1) if m.target_amount > 0 else 0
        out.append(MilestoneOut(
            **{col.name: getattr(m, col.name) for col in m.__table__.columns},
            progress_percent=pct,
        ))
    return out


@milestones_router.post("/", response_model=MilestoneOut)
async def create_milestone(
    data: MilestoneCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    m = Milestone(**data.model_dump())
    db.add(m)
    await db.flush()
    await db.refresh(m)
    return MilestoneOut(
        **{col.name: getattr(m, col.name) for col in m.__table__.columns},
        progress_percent=0.0,
    )


@milestones_router.delete("/{m_id}")
async def delete_milestone(
    m_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Milestone).where(Milestone.id == m_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Цель не найдена")
    await db.delete(m)
    return {"ok": True}


# ── Monthly Stats ─────────────────────────────────────────────────────────────

@stats_router.get("/")
async def list_stats(
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from datetime import datetime
    if not year:
        year = datetime.now().year
    result = await db.execute(
        select(MonthlyStats).where(MonthlyStats.year == year).order_by(MonthlyStats.month)
    )
    return result.scalars().all()


@stats_router.put("/{year}/{month}", response_model=MonthlyStatsOut)
async def upsert_stats(
    year: int,
    month: int,
    data: MonthlyStatsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_editor),
):
    result = await db.execute(
        select(MonthlyStats).where(MonthlyStats.year == year, MonthlyStats.month == month)
    )
    stats = result.scalar_one_or_none()
    if not stats:
        stats = MonthlyStats(year=year, month=month)
        db.add(stats)

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(stats, field, value)
    await db.flush()
    await db.refresh(stats)
    return stats
