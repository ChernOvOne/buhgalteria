from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import date, timedelta
from typing import Optional

from app.database import get_db
from app.models import (
    Transaction, TransactionType, Category, Partner, InkasRecord,
    AdCampaign, AppSettings, User,
)
from app.schemas import ReportRequest
from app.core.dependencies import get_current_user
from app.services.report_service import generate_pdf_report, generate_excel_report

router = APIRouter(prefix="/reports", tags=["reports"])


async def collect_report_data(db: AsyncSession, date_from: date, date_to: date):
    # Транзакции
    t_result = await db.execute(
        select(Transaction)
        .where(and_(Transaction.date >= date_from, Transaction.date <= date_to))
        .order_by(Transaction.date)
    )
    transactions = t_result.scalars().all()

    # Обогащаем категориями
    trans_dicts = []
    for t in transactions:
        cat = None
        if t.category_id:
            c_r = await db.execute(select(Category).where(Category.id == t.category_id))
            c = c_r.scalar_one_or_none()
            cat = {"id": c.id, "name": c.name, "color": c.color, "icon": c.icon,
                   "is_active": c.is_active, "sort_order": c.sort_order} if c else None
        trans_dicts.append({
            "id": t.id, "type": str(t.type.value), "amount": t.amount,
            "date": t.date, "category": cat,
            "description": t.description, "receipt_url": t.receipt_url,
            "receipt_file": t.receipt_file, "is_historical": t.is_historical,
            "created_at": t.created_at,
        })

    # Расходы по категориям
    from sqlalchemy import func
    cat_result = await db.execute(
        select(Category.name, Category.color, func.sum(Transaction.amount).label("total"))
        .join(Transaction, Transaction.category_id == Category.id)
        .where(and_(
            Transaction.type == TransactionType.expense,
            Transaction.date >= date_from,
            Transaction.date <= date_to,
        ))
        .group_by(Category.id, Category.name, Category.color)
        .order_by(func.sum(Transaction.amount).desc())
    )
    expense_by_cat = [
        {"name": r[0], "color": r[1], "amount": float(r[2])}
        for r in cat_result.all()
    ]

    # Партнёры
    p_result = await db.execute(select(Partner).where(Partner.is_active == True))
    partners = p_result.scalars().all()
    partners_summary = []
    for p in partners:
        last_dvd_r = await db.execute(
            select(InkasRecord)
            .where(and_(InkasRecord.partner_id == p.id,
                        InkasRecord.date >= date_from,
                        InkasRecord.date <= date_to))
            .order_by(InkasRecord.date.desc()).limit(1)
        )
        last_dvd = last_dvd_r.scalar_one_or_none()
        partners_summary.append({
            "name": p.name,
            "role_label": p.role_label,
            "last_dividend": last_dvd.amount if last_dvd else None,
            "remaining_debt": max(0, p.initial_investment - p.initial_returned),
        })

    # Инкас
    ink_result = await db.execute(
        select(InkasRecord)
        .where(and_(InkasRecord.date >= date_from, InkasRecord.date <= date_to))
        .order_by(InkasRecord.date)
    )
    inkas = ink_result.scalars().all()
    inkas_dicts = []
    for r in inkas:
        p_name = ""
        if r.partner_id:
            pr = await db.execute(select(Partner).where(Partner.id == r.partner_id))
            pp = pr.scalar_one_or_none()
            p_name = pp.name if pp else ""
        inkas_dicts.append({
            "id": r.id, "date": r.date, "month_label": r.month_label,
            "type": str(r.type.value), "amount": r.amount,
            "partner_name": p_name, "description": r.description,
            "created_at": r.created_at,
        })

    # Реклама
    ad_result = await db.execute(
        select(AdCampaign)
        .where(and_(AdCampaign.date >= date_from, AdCampaign.date <= date_to))
        .order_by(AdCampaign.date)
    )
    ads = ad_result.scalars().all()
    ads_dicts = []
    for a in ads:
        cps = round(a.amount / a.subscribers_gained, 2) if a.subscribers_gained and a.subscribers_gained > 0 else None
        ads_dicts.append({
            **{col.name: getattr(a, col.name) for col in a.__table__.columns},
            "cost_per_sub": cps,
        })

    # Компания
    cn_r = await db.execute(select(AppSettings).where(AppSettings.key == "company_name"))
    cn_row = cn_r.scalar_one_or_none()
    company_name = cn_row.value if cn_row and cn_row.value else "Мой бизнес"

    # KPI
    income = sum(t["amount"] for t in trans_dicts if t["type"] == "income")
    expense = sum(t["amount"] for t in trans_dicts if t["type"] == "expense")
    days = (date_to - date_from).days + 1
    kpi = {
        "income": income,
        "expense": expense,
        "profit": income - expense,
        "avg_per_day": round(income / days, 2) if days > 0 else 0,
    }

    return company_name, kpi, trans_dicts, expense_by_cat, partners_summary, inkas_dicts, ads_dicts


@router.post("/pdf")
async def export_pdf(
    data: ReportRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    company_name, kpi, transactions, expense_by_cat, partners_summary, inkas, ads = \
        await collect_report_data(db, data.date_from, data.date_to)

    period_label = f"{data.date_from.strftime('%d.%m.%Y')} — {data.date_to.strftime('%d.%m.%Y')}"

    pdf_bytes = generate_pdf_report(
        company_name=company_name,
        period_label=period_label,
        kpi=kpi,
        transactions=transactions,
        expense_by_category=expense_by_cat,
        partners_summary=partners_summary,
    )

    filename = f"report_{data.date_from}_{data.date_to}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/excel")
async def export_excel(
    data: ReportRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    company_name, kpi, transactions, expense_by_cat, partners_summary, inkas, ads = \
        await collect_report_data(db, data.date_from, data.date_to)

    xlsx_bytes = generate_excel_report(
        company_name=company_name,
        date_from=data.date_from,
        date_to=data.date_to,
        transactions=transactions,
        expense_by_category=expense_by_cat,
        inkas_records=inkas,
        ad_campaigns=ads,
    )

    filename = f"report_{data.date_from}_{data.date_to}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/quick/{period}")
async def quick_report(
    period: str,  # today | week | month | year
    format: str = "pdf",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    today = date.today()
    if period == "today":
        date_from = date_to = today
    elif period == "week":
        date_from = today - timedelta(days=6)
        date_to = today
    elif period == "month":
        date_from = today.replace(day=1)
        date_to = today
    elif period == "year":
        date_from = today.replace(month=1, day=1)
        date_to = today
    else:
        date_from = date_to = today

    req = ReportRequest(date_from=date_from, date_to=date_to, format=format)
    if format == "excel":
        return await export_excel(req, db, None)
    return await export_pdf(req, db, None)
