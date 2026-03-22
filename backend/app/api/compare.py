from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional
from datetime import date
from pydantic import BaseModel

from app.database import get_db
from app.models import (
    Transaction, TransactionType, Category, InkasRecord, InkasType,
    Partner, AdCampaign, Payment, AppSettings, User,
)
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/compare", tags=["compare"])


class ComparePeriod(BaseModel):
    a_from: date
    a_to:   date
    b_from: date
    b_to:   date


async def _fetch_period_data(db: AsyncSession, d_from: date, d_to: date) -> dict:
    """Собирает все данные за период."""

    # KPI
    kpi_r = await db.execute(
        select(Transaction.type, func.sum(Transaction.amount))
        .where(and_(Transaction.date >= d_from, Transaction.date <= d_to))
        .group_by(Transaction.type)
    )
    rows = kpi_r.all()
    income  = float(sum(r[1] for r in rows if r[0] == TransactionType.income) or 0)
    expense = float(sum(r[1] for r in rows if r[0] == TransactionType.expense) or 0)
    days = (d_to - d_from).days + 1

    # Лучший день
    daily_r = await db.execute(
        select(Transaction.date, func.sum(Transaction.amount))
        .where(and_(
            Transaction.type == TransactionType.income,
            Transaction.date >= d_from, Transaction.date <= d_to,
        ))
        .group_by(Transaction.date)
    )
    daily = {str(r[0]): float(r[1]) for r in daily_r.all()}
    best_day = max(daily, key=daily.get) if daily else None

    # График по дням
    chart = [{"date": k, "amount": v} for k, v in sorted(daily.items())]

    # Расходы по категориям
    cat_r = await db.execute(
        select(Category.name, Category.color, func.sum(Transaction.amount).label("total"))
        .join(Transaction, Transaction.category_id == Category.id)
        .where(and_(
            Transaction.type == TransactionType.expense,
            Transaction.date >= d_from, Transaction.date <= d_to,
        ))
        .group_by(Category.id, Category.name, Category.color)
        .order_by(func.sum(Transaction.amount).desc())
    )
    expense_by_cat = [
        {"name": r[0], "color": r[1], "amount": round(float(r[2]), 2)}
        for r in cat_r.all()
    ]

    # Инкас
    ink_r = await db.execute(
        select(InkasRecord.type, Partner.name, func.sum(InkasRecord.amount))
        .join(Partner, InkasRecord.partner_id == Partner.id)
        .where(and_(InkasRecord.date >= d_from, InkasRecord.date <= d_to))
        .group_by(InkasRecord.type, Partner.id, Partner.name)
    )
    inkas = [
        {"type": str(r[0].value), "partner": r[1], "amount": float(r[2])}
        for r in ink_r.all()
    ]
    inkas_total_dvd = sum(i["amount"] for i in inkas if i["type"] == "dividend")
    inkas_total_ret = sum(i["amount"] for i in inkas if i["type"] == "return_inv")

    # Реклама
    ads_r = await db.execute(
        select(
            func.sum(AdCampaign.amount),
            func.sum(AdCampaign.subscribers_gained),
            func.count(AdCampaign.id),
        )
        .where(and_(AdCampaign.date >= d_from, AdCampaign.date <= d_to))
    )
    ads_row = ads_r.one()
    ad_spend    = float(ads_row[0] or 0)
    ad_subs     = int(ads_row[1] or 0)
    ad_count    = int(ads_row[2] or 0)
    cost_per_sub = round(ad_spend / ad_subs, 2) if ad_subs > 0 else None

    # Платежи VPN
    pay_r = await db.execute(
        select(
            func.sum(Payment.amount),
            func.count(Payment.id),
        )
        .where(and_(Payment.date >= d_from, Payment.date <= d_to))
    )
    pay_row = pay_r.one()
    pay_amount = float(pay_row[0] or 0)
    pay_count  = int(pay_row[1] or 0)

    # По тарифам
    tags_r = await db.execute(
        select(Payment.plan_tag, Payment.plan, func.count(Payment.id), func.sum(Payment.amount))
        .where(and_(Payment.date >= d_from, Payment.date <= d_to))
        .group_by(Payment.plan_tag, Payment.plan)
        .order_by(func.count(Payment.id).desc())
    )
    pay_by_tag = [
        {"tag": r[0], "plan": r[1], "count": r[2], "amount": float(r[3] or 0)}
        for r in tags_r.all()
    ]

    return {
        "kpi": {
            "income":      round(income, 2),
            "expense":     round(expense, 2),
            "profit":      round(income - expense, 2),
            "avg_per_day": round(income / days, 2) if days > 0 else 0,
            "best_day":    best_day,
            "best_day_amount": daily.get(best_day, 0) if best_day else 0,
        },
        "chart":           chart,
        "expense_by_cat":  expense_by_cat,
        "inkas": {
            "items":     inkas,
            "total_dvd": round(inkas_total_dvd, 2),
            "total_ret": round(inkas_total_ret, 2),
        },
        "ads": {
            "spend":        round(ad_spend, 2),
            "subscribers":  ad_subs,
            "count":        ad_count,
            "cost_per_sub": cost_per_sub,
        },
        "payments": {
            "amount":   round(pay_amount, 2),
            "count":    pay_count,
            "by_tag":   pay_by_tag,
        },
        "meta": {
            "date_from": str(d_from),
            "date_to":   str(d_to),
            "days":      days,
        },
    }


def _delta(a: float, b: float) -> dict:
    """Вычисляет изменение A→B."""
    if a == 0:
        return {"abs": round(b, 2), "pct": None, "direction": "up" if b > 0 else "neutral"}
    diff = b - a
    pct  = round(diff / a * 100, 1)
    return {
        "abs": round(diff, 2),
        "pct": pct,
        "direction": "up" if diff > 0 else ("down" if diff < 0 else "neutral"),
    }


@router.post("/")
async def compare_periods(
    req: ComparePeriod,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    a_data = await _fetch_period_data(db, req.a_from, req.a_to)
    b_data = await _fetch_period_data(db, req.b_from, req.b_to)

    # Считаем дельты для KPI
    deltas = {
        k: _delta(a_data["kpi"][k], b_data["kpi"][k])
        for k in ["income", "expense", "profit", "avg_per_day"]
    }

    # Категории объединяем
    all_cats = list({c["name"] for c in a_data["expense_by_cat"]} |
                   {c["name"] for c in b_data["expense_by_cat"]})
    a_cat_map = {c["name"]: c for c in a_data["expense_by_cat"]}
    b_cat_map = {c["name"]: c for c in b_data["expense_by_cat"]}
    cat_compare = []
    for name in all_cats:
        a_amt = a_cat_map.get(name, {}).get("amount", 0)
        b_amt = b_cat_map.get(name, {}).get("amount", 0)
        color = a_cat_map.get(name, b_cat_map.get(name, {})).get("color", "#888780")
        cat_compare.append({
            "name": name, "color": color,
            "a": a_amt, "b": b_amt,
            "delta": _delta(a_amt, b_amt),
        })
    cat_compare.sort(key=lambda x: max(x["a"], x["b"]), reverse=True)

    # Компания
    company_r = await db.execute(
        select(AppSettings).where(AppSettings.key == "company_name")
    )
    company_row = company_r.scalar_one_or_none()
    company = company_row.value if company_row else "Бухгалтерия"

    return {
        "company": company,
        "a": a_data,
        "b": b_data,
        "deltas": deltas,
        "cat_compare": cat_compare,
    }


@router.post("/send-telegram")
async def send_compare_to_telegram(
    req: ComparePeriod,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Отправляет сравнительный отчёт в Telegram + PDF."""
    a_data = await _fetch_period_data(db, req.a_from, req.a_to)
    b_data = await _fetch_period_data(db, req.b_from, req.b_to)

    company_r = await db.execute(
        select(AppSettings).where(AppSettings.key == "company_name")
    )
    company_row = company_r.scalar_one_or_none()
    company = company_row.value if company_row else "Бухгалтерия"

    tok_r = await db.execute(select(AppSettings).where(AppSettings.key == "tg_bot_token"))
    tok = tok_r.scalar_one_or_none()
    if not tok or not tok.value:
        return {"ok": False, "error": "Токен бота не настроен"}

    ch_r = await db.execute(select(AppSettings).where(AppSettings.key == "tg_channel_id"))
    ch = ch_r.scalar_one_or_none()
    if not ch or not ch.value:
        return {"ok": False, "error": "Канал не настроен"}

    # Текстовая сводка
    def fmt(v): return "{:,.0f} ₽".format(v).replace(",", " ")
    def arrow(a, b):
        if b > a: return "📈"
        if b < a: return "📉"
        return "➡️"

    text = (
        f"📊 <b>Сравнение периодов — {company}</b>\n\n"
        f"<b>Период A:</b> {req.a_from.strftime('%d.%m.%Y')} — {req.a_to.strftime('%d.%m.%Y')}\n"
        f"<b>Период B:</b> {req.b_from.strftime('%d.%m.%Y')} — {req.b_to.strftime('%d.%m.%Y')}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{arrow(a_data['kpi']['income'], b_data['kpi']['income'])} Доход:   A {fmt(a_data['kpi']['income'])} → B <b>{fmt(b_data['kpi']['income'])}</b>\n"
        f"{arrow(a_data['kpi']['expense'], b_data['kpi']['expense'])} Расход:  A {fmt(a_data['kpi']['expense'])} → B <b>{fmt(b_data['kpi']['expense'])}</b>\n"
        f"{arrow(a_data['kpi']['profit'], b_data['kpi']['profit'])} Прибыль: A {fmt(a_data['kpi']['profit'])} → B <b>{fmt(b_data['kpi']['profit'])}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💳 Платежи: A {a_data['payments']['count']} шт/{fmt(a_data['payments']['amount'])} → B {b_data['payments']['count']} шт/<b>{fmt(b_data['payments']['amount'])}</b>\n"
        f"📢 Реклама: A {fmt(a_data['ads']['spend'])} → B <b>{fmt(b_data['ads']['spend'])}</b>\n"
        f"💸 Инкас:   A {fmt(a_data['inkas']['total_dvd'] + a_data['inkas']['total_ret'])} → B <b>{fmt(b_data['inkas']['total_dvd'] + b_data['inkas']['total_ret'])}</b>"
    )

    # Дельты для общего PDF
    def _d(av, bv):
        if av == 0:
            return {"abs": round(bv,2), "pct": None, "direction": "up" if bv>0 else "neutral"}
        diff = bv - av
        pct = round(diff/av*100, 1)
        return {"abs": round(diff,2), "pct": pct, "direction": "up" if diff>0 else ("down" if diff<0 else "neutral")}

    deltas = {k: _d(a_data["kpi"][k], b_data["kpi"][k])
              for k in ["income","expense","profit","avg_per_day"]}

    all_cats = list({c["name"] for c in a_data["expense_by_cat"]} |
                   {c["name"] for c in b_data["expense_by_cat"]})
    a_cm = {c["name"]: c for c in a_data["expense_by_cat"]}
    b_cm = {c["name"]: c for c in b_data["expense_by_cat"]}
    cat_compare = sorted([
        {"name": n, "color": a_cm.get(n, b_cm.get(n, {})).get("color","#888780"),
         "a": a_cm.get(n,{}).get("amount",0), "b": b_cm.get(n,{}).get("amount",0),
         "delta": _d(a_cm.get(n,{}).get("amount",0), b_cm.get(n,{}).get("amount",0))}
        for n in all_cats
    ], key=lambda x: max(x["a"],x["b"]), reverse=True)

    # Генерируем общий сравнительный PDF
    from app.services.compare_pdf import generate_compare_pdf
    label_a = f"A: {req.a_from} — {req.a_to}"
    label_b = f"B: {req.b_from} — {req.b_to}"
    pdf_bytes = generate_compare_pdf(
        company=company, a=a_data, b=b_data,
        deltas=deltas, cat_compare=cat_compare,
        label_a=label_a, label_b=label_b,
    )

    import httpx
    bot_token = tok.value
    channel_id = ch.value

    async with httpx.AsyncClient(timeout=60) as client:
        # Текстовая сводка
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": channel_id, "text": text, "parse_mode": "HTML"},
        )
        # Общий PDF
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendDocument",
            data={"chat_id": channel_id,
                  "caption": f"📊 Сравнительный отчёт · {company}\n{label_a} vs {label_b}"},
            files={"document": (f"compare_{req.a_from}_{req.b_from}.pdf", pdf_bytes, "application/pdf")},
        )

    return {"ok": True}


@router.post("/pdf")
async def download_compare_pdf(
    req: ComparePeriod,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Генерирует и отдаёт общий сравнительный PDF."""
    from fastapi.responses import Response

    a_data = await _fetch_period_data(db, req.a_from, req.a_to)
    b_data = await _fetch_period_data(db, req.b_from, req.b_to)

    company_r = await db.execute(
        select(AppSettings).where(AppSettings.key == "company_name")
    )
    company_row = company_r.scalar_one_or_none()
    company = company_row.value if company_row else "Бухгалтерия"

    # Дельты
    def _delta(a_val, b_val):
        if a_val == 0:
            return {"abs": round(b_val, 2), "pct": None, "direction": "up" if b_val > 0 else "neutral"}
        diff = b_val - a_val
        pct  = round(diff / a_val * 100, 1)
        return {"abs": round(diff, 2), "pct": pct,
                "direction": "up" if diff > 0 else ("down" if diff < 0 else "neutral")}

    deltas = {k: _delta(a_data["kpi"][k], b_data["kpi"][k])
              for k in ["income", "expense", "profit", "avg_per_day"]}

    all_cats = list({c["name"] for c in a_data["expense_by_cat"]} |
                   {c["name"] for c in b_data["expense_by_cat"]})
    a_cat_map = {c["name"]: c for c in a_data["expense_by_cat"]}
    b_cat_map = {c["name"]: c for c in b_data["expense_by_cat"]}
    cat_compare = []
    for name in all_cats:
        a_amt = a_cat_map.get(name, {}).get("amount", 0)
        b_amt = b_cat_map.get(name, {}).get("amount", 0)
        color = a_cat_map.get(name, b_cat_map.get(name, {})).get("color", "#888780")
        cat_compare.append({"name": name, "color": color, "a": a_amt, "b": b_amt,
                             "delta": _delta(a_amt, b_amt)})
    cat_compare.sort(key=lambda x: max(x["a"], x["b"]), reverse=True)

    from app.services.compare_pdf import generate_compare_pdf
    label_a = f"A: {req.a_from} — {req.a_to}"
    label_b = f"B: {req.b_from} — {req.b_to}"

    pdf_bytes = generate_compare_pdf(
        company=company,
        a=a_data, b=b_data,
        deltas=deltas,
        cat_compare=cat_compare,
        label_a=label_a,
        label_b=label_b,
    )

    filename = f"compare_{req.a_from}_{req.b_from}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
