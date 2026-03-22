from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from typing import Optional
from datetime import date, timedelta
import secrets

from app.database import get_db
from app.models import AdCampaign, UtmClick, UtmLead, Payment, AppSettings, User
from app.core.dependencies import get_current_user

router = APIRouter(tags=["utm"])


# ── Redirect endpoint ─────────────────────────────────────────────────────────

@router.get("/go/{utm_code}")
async def utm_redirect(
    utm_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Основной редирект. Фиксирует клик и перенаправляет на target_url.
    Используется в рекламе вместо прямой ссылки.
    """
    # Ищем кампанию по utm_code
    result = await db.execute(
        select(AdCampaign).where(AdCampaign.utm_code == utm_code)
    )
    campaign = result.scalar_one_or_none()

    # Определяем куда редиректить
    if campaign and campaign.target_url:
        target = campaign.target_url
        # Для бота добавляем start-параметр
        if campaign.target_type == "bot":
            base = target.rstrip("/")
            if "?start=" not in base:
                target = f"{base}?start={utm_code}"
    else:
        # Fallback — главная страница
        target = "https://t.me"

    # Записываем клик
    click = UtmClick(
        utm_code=utm_code,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
    )
    db.add(click)
    await db.commit()

    return RedirectResponse(url=target, status_code=302)


# ── Lead intake (from LEADTEH / VPN bot) ─────────────────────────────────────

class LeadPayload(BaseModel):
    utm_code: str
    customer_id: Optional[str] = None       # Telegram ID
    customer_name: Optional[str] = None
    username: Optional[str] = None
    extra_data: Optional[dict] = None       # любые доп поля


@router.post("/api/utm/lead")
async def receive_lead(
    payload: LeadPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Принимает лида от LEADTEH или VPN-бота.
    Вызывается когда пользователь запускает бота через UTM-ссылку.
    Не требует API-ключа — только utm_code.
    """
    # Проверяем что кампания существует
    result = await db.execute(
        select(AdCampaign).where(AdCampaign.utm_code == payload.utm_code)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        # Принимаем даже если кампания не найдена — не блокируем
        pass

    # Проверяем дубли по customer_id + utm_code
    if payload.customer_id:
        dup = await db.execute(
            select(UtmLead).where(
                and_(
                    UtmLead.utm_code == payload.utm_code,
                    UtmLead.customer_id == payload.customer_id,
                )
            )
        )
        if dup.scalar_one_or_none():
            return {"ok": True, "status": "duplicate"}

    lead = UtmLead(
        utm_code=payload.utm_code,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        username=payload.username,
        extra_data=payload.extra_data,
    )
    db.add(lead)

    # Если у этого customer_id уже есть оплата — помечаем как конвертированного
    if payload.customer_id:
        pay_r = await db.execute(
            select(Payment).where(Payment.customer_id == payload.customer_id).limit(1)
        )
        if pay_r.scalar_one_or_none():
            lead.converted = True

    await db.commit()

    # Уведомление в Telegram о новом лиде
    try:
        from app.services.notification_service import _send_message
        tok_r = await db.execute(
            select(AppSettings).where(AppSettings.key == "tg_bot_token")
        )
        tok = tok_r.scalar_one_or_none()
        ch_r = await db.execute(
            select(AppSettings).where(AppSettings.key == "tg_channel_id")
        )
        ch = ch_r.scalar_one_or_none()
        name_r = await db.execute(
            select(AppSettings).where(AppSettings.key == "company_name")
        )
        company = (name_r.scalar_one_or_none() or type("x", (), {"value": "Бухгалтерия"})()).value

        if tok and tok.value and ch and ch.value and campaign:
            text = (
                f"🎯 <b>Новый лид</b>\n"
                f"Кампания: {campaign.channel_name or utm_code}\n"
                f"Имя: {payload.customer_name or '—'}\n"
                f"TG: @{payload.username or '—'} (<code>{payload.customer_id or '—'}</code>)\n"
                f"<i>{company}</i>"
            )
            import asyncio
            asyncio.ensure_future(_send_message(tok.value, ch.value, text))
    except Exception:
        pass

    return {"ok": True, "status": "created"}


# ── UTM Statistics ────────────────────────────────────────────────────────────

@router.get("/api/utm/stats/{utm_code}")
async def utm_stats(
    utm_code: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Детальная статистика по одной UTM-ссылке."""
    clicks_r = await db.execute(
        select(func.count(UtmClick.id)).where(UtmClick.utm_code == utm_code)
    )
    leads_r = await db.execute(
        select(func.count(UtmLead.id)).where(UtmLead.utm_code == utm_code)
    )
    converted_r = await db.execute(
        select(func.count(UtmLead.id)).where(
            and_(UtmLead.utm_code == utm_code, UtmLead.converted == True)
        )
    )

    # Клики по дням (последние 30)
    from datetime import datetime
    thirty_ago = date.today() - timedelta(days=29)
    daily_r = await db.execute(
        select(
            func.date_trunc("day", UtmClick.created_at).label("day"),
            func.count(UtmClick.id).label("cnt")
        )
        .where(and_(
            UtmClick.utm_code == utm_code,
            UtmClick.created_at >= thirty_ago,
        ))
        .group_by(func.date_trunc("day", UtmClick.created_at))
        .order_by(func.date_trunc("day", UtmClick.created_at))
    )
    daily_clicks = [{"date": str(r[0])[:10], "clicks": r[1]} for r in daily_r.all()]

    # Последние лиды
    leads_list_r = await db.execute(
        select(UtmLead)
        .where(UtmLead.utm_code == utm_code)
        .order_by(UtmLead.created_at.desc())
        .limit(20)
    )
    leads_list = [
        {
            "id": l.id,
            "customer_id": l.customer_id,
            "customer_name": l.customer_name,
            "username": l.username,
            "converted": l.converted,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in leads_list_r.scalars().all()
    ]

    # Выручка по этой кампании (через customer_id → payments)
    lead_customer_ids_r = await db.execute(
        select(UtmLead.customer_id).where(
            and_(UtmLead.utm_code == utm_code, UtmLead.customer_id != None)
        )
    )
    cust_ids = [r[0] for r in lead_customer_ids_r.all()]
    revenue = 0.0
    payment_count = 0
    if cust_ids:
        rev_r = await db.execute(
            select(func.sum(Payment.amount), func.count(Payment.id))
            .where(Payment.customer_id.in_(cust_ids))
        )
        rev_row = rev_r.one()
        revenue = float(rev_row[0] or 0)
        payment_count = int(rev_row[1] or 0)

    clicks = clicks_r.scalar() or 0
    leads = leads_r.scalar() or 0
    converted = converted_r.scalar() or 0

    return {
        "utm_code": utm_code,
        "clicks": clicks,
        "leads": leads,
        "converted": converted,
        "payments": payment_count,
        "revenue": round(revenue, 2),
        "click_to_lead_pct": round(leads / clicks * 100, 1) if clicks > 0 else 0,
        "lead_to_pay_pct":   round(converted / leads * 100, 1) if leads > 0 else 0,
        "daily_clicks": daily_clicks,
        "leads_list": leads_list,
    }


@router.get("/api/utm/summary")
async def utm_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Сводка по всем UTM-кампаниям для дашборда."""
    today = date.today()

    # Лиды сегодня
    leads_today_r = await db.execute(
        select(func.count(UtmLead.id))
        .where(func.date(UtmLead.created_at) == today)
    )

    # Клики сегодня
    clicks_today_r = await db.execute(
        select(func.count(UtmClick.id))
        .where(func.date(UtmClick.created_at) == today)
    )

    # Топ кампаний по лидам за последние 30 дней
    thirty_ago = today - timedelta(days=29)
    top_r = await db.execute(
        select(UtmLead.utm_code, func.count(UtmLead.id).label("leads_cnt"))
        .where(UtmLead.created_at >= thirty_ago)
        .group_by(UtmLead.utm_code)
        .order_by(func.count(UtmLead.id).desc())
        .limit(5)
    )

    top_campaigns = []
    for utm_code, leads_cnt in top_r.all():
        # Ищем кампанию
        camp_r = await db.execute(
            select(AdCampaign).where(AdCampaign.utm_code == utm_code)
        )
        camp = camp_r.scalar_one_or_none()

        # Оплаты
        lead_ids_r = await db.execute(
            select(UtmLead.customer_id).where(
                and_(UtmLead.utm_code == utm_code, UtmLead.customer_id != None,
                     UtmLead.converted == True)
            )
        )
        cids = [r[0] for r in lead_ids_r.all()]
        revenue = 0.0
        if cids:
            rev_r = await db.execute(
                select(func.sum(Payment.amount)).where(Payment.customer_id.in_(cids))
            )
            revenue = float(rev_r.scalar() or 0)

        top_campaigns.append({
            "utm_code": utm_code,
            "campaign_name": camp.channel_name if camp else utm_code,
            "leads": leads_cnt,
            "revenue": round(revenue, 2),
            "amount": camp.amount if camp else 0,
            "roi": round((revenue - (camp.amount or 0)) / (camp.amount or 1) * 100, 1) if camp and camp.amount else 0,
        })

    return {
        "leads_today": leads_today_r.scalar() or 0,
        "clicks_today": clicks_today_r.scalar() or 0,
        "top_campaigns": top_campaigns,
    }


# ── Generate UTM code ─────────────────────────────────────────────────────────

def generate_utm_code() -> str:
    return "ad_" + secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]
