from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.models import Partner, InkasRecord, InkasType, User, UserRole
from app.schemas import (
    PartnerCreate, PartnerUpdate, PartnerOut, PartnerDetail, PartnerStats,
    InkasRecordCreate, InkasRecordOut,
)
from app.services.notification_service import notify, format_inkas
from app.core.dependencies import require_admin, require_editor, get_current_user

router = APIRouter(prefix="/partners", tags=["partners"])


async def calc_partner_stats(partner: Partner, db: AsyncSession) -> PartnerStats:
    result = await db.execute(
        select(InkasRecord)
        .where(InkasRecord.partner_id == partner.id)
        .order_by(InkasRecord.date.desc())
    )
    records = result.scalars().all()

    total_invested = partner.initial_investment
    total_returned = partner.initial_returned
    total_dividends = partner.initial_dividends

    dvd_amounts = []
    for r in records:
        if r.type == InkasType.investment:
            total_invested += r.amount
        elif r.type == InkasType.return_inv:
            total_returned += r.amount
        elif r.type == InkasType.dividend:
            total_dividends += r.amount
            dvd_amounts.append(r.amount)

    remaining_debt = max(0.0, total_invested - total_returned)
    avg_dividend = sum(dvd_amounts) / len(dvd_amounts) if dvd_amounts else 0.0

    last_dvd = next((r for r in records if r.type == InkasType.dividend), None)

    # Прогноз следующей выплаты — среднее последних 3 дивидендов
    forecast = None
    last3 = [r.amount for r in records if r.type == InkasType.dividend][:3]
    if last3:
        forecast = sum(last3) / len(last3)

    return PartnerStats(
        total_invested=total_invested,
        total_returned=total_returned,
        remaining_debt=remaining_debt,
        total_dividends=total_dividends,
        avg_dividend=avg_dividend,
        last_dividend_amount=last_dvd.amount if last_dvd else None,
        last_dividend_date=last_dvd.date if last_dvd else None,
        forecast_next=forecast,
        records=[InkasRecordOut.model_validate(r) for r in records],
    )


@router.get("/", response_model=List[PartnerOut])
async def list_partners(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Partner).where(Partner.is_active == True).order_by(Partner.name)
    # Инвестор и партнёр видят только себя
    if current_user.role in (UserRole.investor, UserRole.partner):
        if current_user.partner_id:
            q = q.where(Partner.id == current_user.partner_id)
        else:
            return []
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=PartnerOut)
async def create_partner(
    data: PartnerCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    partner = Partner(**data.model_dump())
    db.add(partner)
    await db.flush()
    await db.refresh(partner)
    return partner


@router.get("/{partner_id}", response_model=PartnerDetail)
async def get_partner(
    partner_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Партнёры/инвесторы видят только себя
    if current_user.role in (UserRole.investor, UserRole.partner):
        if current_user.partner_id != partner_id:
            raise HTTPException(status_code=403, detail="Нет доступа")

    result = await db.execute(select(Partner).where(Partner.id == partner_id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail="Партнёр не найден")

    stats = await calc_partner_stats(partner, db)

    # Скрываем заметки от самого партнёра
    if current_user.role in (UserRole.investor, UserRole.partner):
        partner.notes = None

    return PartnerDetail(
        **PartnerOut.model_validate(partner).model_dump(),
        stats=stats,
    )


@router.patch("/{partner_id}", response_model=PartnerOut)
async def update_partner(
    partner_id: str,
    data: PartnerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Partner).where(Partner.id == partner_id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail="Партнёр не найден")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(partner, field, value)
    return partner


@router.delete("/{partner_id}")
async def delete_partner(
    partner_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Partner).where(Partner.id == partner_id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail="Партнёр не найден")
    partner.is_active = False
    return {"ok": True}


# ── Inkas Records ─────────────────────────────────────────────────────────────

@router.post("/inkas", response_model=InkasRecordOut)
async def create_inkas(
    data: InkasRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    result = await db.execute(select(Partner).where(Partner.id == data.partner_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Партнёр не найден")

    record = InkasRecord(**data.model_dump(), created_by=current_user.id)
    db.add(record)
    await db.flush()
    await db.refresh(record)

    # Уведомление
    try:
        from app.models import AppSettings
        from sqlalchemy import select as _select
        company_r = await db.execute(_select(AppSettings).where(AppSettings.key == "company_name"))
        company_row = company_r.scalar_one_or_none()
        company = company_row.value if company_row else "Бухгалтерия"
        partner_r = await db.execute(_select(Partner).where(Partner.id == data.partner_id))
        partner = partner_r.scalar_one_or_none()
        text = format_inkas(
            inkas_type=str(data.type.value),
            amount=data.amount,
            partner_name=partner.name if partner else "?",
            month_label=data.month_label,
            description=data.description,
            user_name=current_user.full_name or current_user.username,
            company=company,
        )
        import asyncio as _asyncio
        _asyncio.ensure_future(notify(db, "inkas", text))
    except Exception:
        pass

    return record


@router.get("/inkas/all", response_model=List[InkasRecordOut])
async def list_all_inkas(
    partner_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(InkasRecord).order_by(InkasRecord.date.desc())
    if partner_id:
        q = q.where(InkasRecord.partner_id == partner_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.delete("/inkas/{record_id}")
async def delete_inkas(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_editor),
):
    result = await db.execute(select(InkasRecord).where(InkasRecord.id == record_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    await db.delete(r)
    return {"ok": True}
