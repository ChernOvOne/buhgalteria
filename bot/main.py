"""Buhgalteria Telegram Bot — aiogram 3"""
import asyncio, logging, os, sys
from datetime import date, timedelta, datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

from app.database import AsyncSessionLocal
from app.models import (
    Transaction, TransactionType, Partner, InkasRecord, InkasType,
    AppSettings, Payment,
)
from sqlalchemy import select, func, and_
from app.services.report_service import generate_pdf_report, generate_excel_report


# ── Helpers ───────────────────────────────────────────────────────────────────
async def gs(db, key, default=None):
    r = await db.execute(select(AppSettings).where(AppSettings.key == key))
    row = r.scalar_one_or_none()
    return row.value if row else default

def fmt(v): return "{:,.0f} ₽".format(v).replace(",", " ") if v else "0 ₽"

async def check_access(db, uid):
    raw = await gs(db, "tg_allowed_ids", "")
    if not raw:
        admin = await gs(db, "tg_admin_id", "")
        return not admin or str(uid) == admin
    return str(uid) in [x.strip() for x in raw.replace(";",",").split(",")]

async def get_kpi(db, d_from, d_to):
    r = await db.execute(
        select(Transaction.type, func.sum(Transaction.amount))
        .where(and_(Transaction.date >= d_from, Transaction.date <= d_to))
        .group_by(Transaction.type)
    )
    rows = r.all()
    inc = float(sum(row[1] for row in rows if row[0] == TransactionType.income) or 0)
    exp = float(sum(row[1] for row in rows if row[0] == TransactionType.expense) or 0)
    return {"income": inc, "expense": exp, "profit": inc - exp}

async def get_partner_debts(db):
    pr = await db.execute(select(Partner).where(Partner.is_active == True))
    result = []
    for p in pr.scalars().all():
        ti = p.initial_investment
        tr = p.initial_returned
        td = p.initial_dividends
        inv = await db.execute(select(func.sum(InkasRecord.amount))
            .where(and_(InkasRecord.partner_id==p.id, InkasRecord.type==InkasType.investment)))
        ret = await db.execute(select(func.sum(InkasRecord.amount))
            .where(and_(InkasRecord.partner_id==p.id, InkasRecord.type==InkasType.return_inv)))
        dvd = await db.execute(select(func.sum(InkasRecord.amount))
            .where(and_(InkasRecord.partner_id==p.id, InkasRecord.type==InkasType.dividend)))
        ti += float(inv.scalar() or 0)
        tr += float(ret.scalar() or 0)
        td += float(dvd.scalar() or 0)
        result.append({"id": p.id, "name": p.name, "role": p.role_label,
                       "invested": ti, "returned": tr, "dividends": td,
                       "debt": max(0.0, ti - tr)})
    return result

async def get_inkas_summary(db, d_from, d_to):
    r = await db.execute(
        select(InkasRecord, Partner.name)
        .join(Partner, InkasRecord.partner_id == Partner.id)
        .where(and_(InkasRecord.date >= d_from, InkasRecord.date <= d_to))
        .order_by(InkasRecord.date.desc())
    )
    tl = {"dividend":"ДВД","return_inv":"Возврат","investment":"Вложение"}
    return [{"partner": r[1], "type": tl.get(str(r[0].type.value), "?"),
             "amount": float(r[0].amount), "month": r[0].month_label or "",
             "date": str(r[0].date)} for r in r.all()]

async def build_report_text(db, d_from, d_to, label, company):
    kpi = await get_kpi(db, d_from, d_to)
    inkas = await get_inkas_summary(db, d_from, d_to)
    debts = await get_partner_debts(db)
    days = (d_to - d_from).days + 1
    lines = [
        f"📊 <b>{company}</b>",
        f"📅 <b>{label}</b> ({d_from.strftime('%d.%m.%Y')} — {d_to.strftime('%d.%m.%Y')})",
        "", "━━━━━━━━━━━━━━━━━━",
        f"💚 Доход:   <b>{fmt(kpi['income'])}</b>",
        f"❤️ Расход:  <b>{fmt(kpi['expense'])}</b>",
        f"💰 Прибыль: <b>{fmt(kpi['profit'])}</b>",
    ]
    if days > 1:
        lines.append(f"📈 В день:  <b>{fmt(kpi['income']/days)}</b>")
    if inkas:
        lines += ["", "━━━━━━━━━━━━━━━━━━", "💸 <b>Инкас за период:</b>"]
        for rec in inkas[:6]:
            lines.append(f"  • {rec['partner']} — {rec['type']}: {fmt(rec['amount'])}"
                         + (f" ({rec['month']})" if rec['month'] else ""))
    if any(d['debt'] > 0 for d in debts):
        lines += ["", "━━━━━━━━━━━━━━━━━━", "🏦 <b>Остаток долга:</b>"]
        for d in debts:
            if d['debt'] > 0:
                lines.append(f"  • {d['name']}: <b>{fmt(d['debt'])}</b>")
    return "\n".join(lines)


# ── Keyboards ─────────────────────────────────────────────────────────────────
def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📊 Отчёт",    callback_data="menu:report"),
        InlineKeyboardButton(text="💳 Платежи",  callback_data="menu:payments"),
    )
    kb.row(
        InlineKeyboardButton(text="💰 Баланс",   callback_data="menu:balance"),
        InlineKeyboardButton(text="🏦 Партнёры", callback_data="menu:partners"),
    )
    kb.row(
        InlineKeyboardButton(text="📄 PDF",      callback_data="menu:pdf"),
        InlineKeyboardButton(text="📊 Excel",    callback_data="menu:excel"),
    )
    return kb.as_markup()

def period_kb(prefix):
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="Сегодня", callback_data=f"{prefix}:today"),
        InlineKeyboardButton(text="Неделя",  callback_data=f"{prefix}:week"),
    )
    kb.row(
        InlineKeyboardButton(text="Месяц",   callback_data=f"{prefix}:month"),
        InlineKeyboardButton(text="Год",     callback_data=f"{prefix}:year"),
    )
    kb.row(InlineKeyboardButton(text="🏠 Меню", callback_data="menu:back"))
    return kb.as_markup()

def back_kb():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:back"))
    return kb.as_markup()

def partners_list_kb(partners):
    kb = InlineKeyboardBuilder()
    for p in partners:
        kb.row(InlineKeyboardButton(
            text=f"👤 {p['name']} {'✅' if p['debt']==0 else '⚠️'}",
            callback_data=f"partner:{p['id']}"
        ))
    kb.row(InlineKeyboardButton(text="🏠 Меню", callback_data="menu:back"))
    return kb.as_markup()

def partner_detail_kb(partner_id):
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="💸 Инкас",     callback_data=f"pinkas:{partner_id}"),
        InlineKeyboardButton(text="💼 Инвестиции", callback_data=f"pinvest:{partner_id}"),
    )
    kb.row(InlineKeyboardButton(text="🔙 Партнёры", callback_data="menu:partners"))
    return kb.as_markup()

def period_dates(period):
    today = date.today()
    if period == "today":  return today, today, "Сегодня"
    if period == "week":   return today - timedelta(days=6), today, "Неделя"
    if period == "month":  return today.replace(day=1), today, today.strftime("%B %Y")
    if period == "year":   return today.replace(month=1,day=1), today, str(today.year)
    return today, today, "Сегодня"


# ── Bot ───────────────────────────────────────────────────────────────────────
def make_bot():
    token = os.getenv("TG_BOT_TOKEN","")
    if not token: raise ValueError("TG_BOT_TOKEN не задан")
    return Bot(token=token)

dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, message.from_user.id):
            await message.answer("⛔ Доступ запрещён."); return
        company = await gs(db, "company_name", "Бухгалтерия")
    await message.answer(
        f"👋 <b>{company}</b>\n\nВыберите действие:",
        reply_markup=main_menu_kb(), parse_mode="HTML"
    )

@dp.callback_query(F.data == "menu:back")
async def cb_back(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id):
            await call.answer("⛔", show_alert=True); return
        company = await gs(db, "company_name", "Бухгалтерия")
    await call.message.edit_text(
        f"🏠 <b>{company}</b>\n\nВыберите действие:",
        reply_markup=main_menu_kb(), parse_mode="HTML"
    )

# ── Меню ──────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "menu:report")
async def cb_report_menu(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
    await call.message.edit_text("📊 <b>Отчёт</b>\nВыберите период:",
        reply_markup=period_kb("report"), parse_mode="HTML")

@dp.callback_query(F.data == "menu:pdf")
async def cb_pdf_menu(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
    await call.message.edit_text("📄 <b>PDF отчёт</b>\nВыберите период:",
        reply_markup=period_kb("pdf"), parse_mode="HTML")

@dp.callback_query(F.data == "menu:excel")
async def cb_excel_menu(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
    await call.message.edit_text("📊 <b>Excel отчёт</b>\nВыберите период:",
        reply_markup=period_kb("excel"), parse_mode="HTML")

@dp.callback_query(F.data == "menu:balance")
async def cb_balance(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        starting = float(await gs(db,"starting_balance","0") or 0)
        all_inc = await db.execute(select(func.sum(Transaction.amount))
            .where(Transaction.type==TransactionType.income))
        all_exp = await db.execute(select(func.sum(Transaction.amount))
            .where(Transaction.type==TransactionType.expense))
        all_ink = await db.execute(select(func.sum(InkasRecord.amount))
            .where(InkasRecord.type.in_([InkasType.dividend,InkasType.return_inv])))
        balance = starting + float(all_inc.scalar() or 0) - float(all_exp.scalar() or 0) - float(all_ink.scalar() or 0)
        company = await gs(db, "company_name", "Бухгалтерия")
    await call.message.edit_text(
        f"💳 <b>{company}</b>\n\nОстаток на счёте: <b>{fmt(balance)}</b>",
        reply_markup=back_kb(), parse_mode="HTML"
    )

@dp.callback_query(F.data == "menu:payments")
async def cb_payments(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        today = date.today()
        t_r = await db.execute(select(func.sum(Payment.amount), func.count(Payment.id))
            .where(Payment.date==today))
        ta, tc = t_r.one()
        act_r = await db.execute(select(func.count(Payment.id)).where(Payment.sub_end>=today))
        exp_r = await db.execute(select(func.count(Payment.id))
            .where(and_(Payment.sub_end>=today, Payment.sub_end<=today+timedelta(days=3))))
        tags_r = await db.execute(
            select(Payment.plan_tag, Payment.plan, func.count(Payment.id))
            .where(Payment.sub_end>=today)
            .group_by(Payment.plan_tag, Payment.plan)
        )
        tags = tags_r.all()
        company = await gs(db,"company_name","Бухгалтерия")
    lines = [
        f"💳 <b>{company} — Платежи</b>",
        f"📅 Сегодня: <b>{tc or 0}</b> · {fmt(float(ta or 0))}",
        f"✅ Активных: <b>{act_r.scalar() or 0}</b>",
        f"⚠️ Истекают 3д: <b>{exp_r.scalar() or 0}</b>",
    ]
    if tags:
        lines += ["","📊 <b>По тарифам:</b>"]
        for tag, plan, cnt in tags:
            lines.append(f"  • {plan or tag or '?'}: <b>{cnt}</b>")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb(), parse_mode="HTML")


# ── Партнёры ──────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "menu:partners")
async def cb_partners_list(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        debts = await get_partner_debts(db)
        company = await gs(db,"company_name","Бухгалтерия")
    if not debts:
        await call.message.edit_text("Партнёры не найдены", reply_markup=back_kb())
        return
    lines = [f"🏦 <b>{company} — Партнёры</b>\n"]
    for d in debts:
        status = "✅ погашено" if d['debt']==0 else f"долг <b>{fmt(d['debt'])}</b>"
        lines.append(f"👤 <b>{d['name']}</b> ({d['role']})")
        lines.append(f"   Вложено: {fmt(d['invested'])} · Возвращено: {fmt(d['returned'])}")
        lines.append(f"   ДВД выплачено: {fmt(d['dividends'])}")
        lines.append(f"   Статус: {status}\n")
    lines.append("👇 Нажмите на партнёра для деталей:")
    await call.message.edit_text("\n".join(lines),
        reply_markup=partners_list_kb(debts), parse_mode="HTML")


@dp.callback_query(F.data.startswith("partner:"))
async def cb_partner_detail(call: CallbackQuery):
    partner_id = call.data.split(":")[1]
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        p_r = await db.execute(select(Partner).where(Partner.id==partner_id))
        p = p_r.scalar_one_or_none()
        if not p:
            await call.answer("Партнёр не найден"); return
        # Считаем полную статистику
        debts = await get_partner_debts(db)
        d = next((x for x in debts if x['id']==partner_id), None)
        if not d:
            await call.answer("Данные не найдены"); return
        # Последние 5 записей инкаса
        ink_r = await db.execute(
            select(InkasRecord)
            .where(InkasRecord.partner_id==partner_id)
            .order_by(InkasRecord.date.desc())
            .limit(5)
        )
        recent = ink_r.scalars().all()
    tl = {"dividend":"💸 ДВД","return_inv":"🔄 Возврат","investment":"💼 Вложение"}
    lines = [
        f"👤 <b>{p.name}</b> ({p.role_label})",
        "", "━━━━━━━━━━━━━━━━━━",
        f"💼 Всего вложено:    <b>{fmt(d['invested'])}</b>",
        f"🔄 Возвращено:       <b>{fmt(d['returned'])}</b>",
        f"💸 ДВД выплачено:   <b>{fmt(d['dividends'])}</b>",
        f"📊 Остаток долга:   <b>{fmt(d['debt'])}</b>",
    ]
    if recent:
        lines += ["","━━━━━━━━━━━━━━━━━━","📋 <b>Последние операции:</b>"]
        for rec in recent:
            t = tl.get(str(rec.type.value),"?")
            lines.append(f"  {t}: {fmt(rec.amount)} — {str(rec.date)}"
                         + (f" ({rec.month_label})" if rec.month_label else ""))
    await call.message.edit_text("\n".join(lines),
        reply_markup=partner_detail_kb(partner_id), parse_mode="HTML")


@dp.callback_query(F.data.startswith("pinkas:"))
async def cb_partner_inkas(call: CallbackQuery):
    partner_id = call.data.split(":")[1]
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        p_r = await db.execute(select(Partner).where(Partner.id==partner_id))
        p = p_r.scalar_one_or_none()
        ink_r = await db.execute(
            select(InkasRecord)
            .where(and_(InkasRecord.partner_id==partner_id,
                        InkasRecord.type.in_([InkasType.dividend, InkasType.return_inv])))
            .order_by(InkasRecord.date.desc())
            .limit(20)
        )
        records = ink_r.scalars().all()
    tl = {"dividend":"💸 ДВД","return_inv":"🔄 Возврат"}
    lines = [f"💸 <b>Инкас — {p.name if p else '?'}</b>\n"]
    if not records:
        lines.append("Операций нет")
    else:
        total = sum(float(r.amount) for r in records)
        for rec in records:
            t = tl.get(str(rec.type.value),"?")
            lines.append(f"{t} <b>{fmt(rec.amount)}</b> — {str(rec.date)}"
                         + (f"\n   Период: {rec.month_label}" if rec.month_label else "")
                         + (f"\n   {rec.description}" if rec.description else ""))
        lines += ["","━━━━━━━━━━━━━━━━━━", f"Итого: <b>{fmt(total)}</b>"]
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"partner:{partner_id}"))
    await call.message.edit_text("\n".join(lines),
        reply_markup=kb.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data.startswith("pinvest:"))
async def cb_partner_invest(call: CallbackQuery):
    partner_id = call.data.split(":")[1]
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        p_r = await db.execute(select(Partner).where(Partner.id==partner_id))
        p = p_r.scalar_one_or_none()
        inv_r = await db.execute(
            select(InkasRecord)
            .where(and_(InkasRecord.partner_id==partner_id,
                        InkasRecord.type==InkasType.investment))
            .order_by(InkasRecord.date.desc())
            .limit(20)
        )
        records = inv_r.scalars().all()
        # Общая статистика
        d_list = await get_partner_debts(db)
        d = next((x for x in d_list if x['id']==partner_id), {})
    lines = [f"💼 <b>Инвестиции — {p.name if p else '?'}</b>\n"]
    if not records and (d.get('invested',0) == 0):
        lines.append("Вложений нет")
    else:
        if p and p.initial_investment > 0:
            lines.append(f"Начальное вложение: <b>{fmt(p.initial_investment)}</b>")
        for rec in records:
            lines.append(f"💼 <b>{fmt(rec.amount)}</b> — {str(rec.date)}"
                         + (f"\n   {rec.description}" if rec.description else ""))
        lines += ["","━━━━━━━━━━━━━━━━━━",
                  f"Всего вложено:  <b>{fmt(d.get('invested',0))}</b>",
                  f"Возвращено:     <b>{fmt(d.get('returned',0))}</b>",
                  f"Остаток долга:  <b>{fmt(d.get('debt',0))}</b>"]
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"partner:{partner_id}"))
    await call.message.edit_text("\n".join(lines),
        reply_markup=kb.as_markup(), parse_mode="HTML")


# ── Отчёт текстом ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("report:"))
async def cb_report(call: CallbackQuery):
    period = call.data.split(":")[1]
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        d_from, d_to, label = period_dates(period)
        company = await gs(db,"company_name","Бухгалтерия")
        text = await build_report_text(db, d_from, d_to, label, company)
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")


# ── PDF ───────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("pdf:"))
async def cb_pdf(call: CallbackQuery):
    period = call.data.split(":")[1]
    await call.answer("⏳ Генерирую PDF...")
    await call.message.edit_text("⏳ Генерирую PDF отчёт...")
    try:
        async with AsyncSessionLocal() as db:
            if not await check_access(db, call.from_user.id): return
            d_from, d_to, label = period_dates(period)
            company = await gs(db,"company_name","Бухгалтерия")
            kpi = await get_kpi(db, d_from, d_to)
            debts = await get_partner_debts(db)
            from app.models import Category
            cat_r = await db.execute(
                select(Category.name, Category.color, func.sum(Transaction.amount).label("total"))
                .join(Transaction, Transaction.category_id==Category.id)
                .where(and_(Transaction.type==TransactionType.expense,
                            Transaction.date>=d_from, Transaction.date<=d_to))
                .group_by(Category.id, Category.name, Category.color)
                .order_by(func.sum(Transaction.amount).desc())
            )
            exp_by_cat = [{"name":r[0],"color":r[1],"amount":float(r[2])} for r in cat_r.all()]
            partners_summary = [
                {"name": d["name"], "role_label": d["role"],
                 "last_dividend": None, "remaining_debt": d["debt"],
                 "total_invested": d["invested"], "total_dividends": d["dividends"]}
                for d in debts
            ]
            # Инкас за период
            inkas = await get_inkas_summary(db, d_from, d_to)

        days = (d_to - d_from).days + 1
        kpi_data = {**kpi, "avg_per_day": kpi["income"]/days if days>0 else 0}

        pdf_bytes = generate_pdf_report(
            company_name=company,
            period_label=f"{label}: {d_from.strftime('%d.%m.%Y')} — {d_to.strftime('%d.%m.%Y')}",
            kpi=kpi_data,
            transactions=[],
            expense_by_category=exp_by_cat,
            partners_summary=partners_summary,
        )

        await call.message.answer_document(
            BufferedInputFile(pdf_bytes, filename=f"report_{d_from}_{d_to}.pdf"),
            caption=f"📄 {company} — {label}",
        )
        await call.message.delete()
    except Exception as e:
        logger.error(f"PDF error: {e}", exc_info=True)
        await call.message.edit_text(f"❌ Ошибка генерации PDF: {e}\n\nПопробуйте другой период.",
            reply_markup=back_kb())


# ── Excel ─────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("excel:"))
async def cb_excel(call: CallbackQuery):
    period = call.data.split(":")[1]
    await call.answer("⏳ Генерирую Excel...")
    await call.message.edit_text("⏳ Генерирую Excel отчёт...")
    try:
        async with AsyncSessionLocal() as db:
            if not await check_access(db, call.from_user.id): return
            d_from, d_to, label = period_dates(period)
            company = await gs(db,"company_name","Бухгалтерия")

            t_r = await db.execute(
                select(Transaction)
                .where(and_(Transaction.date>=d_from, Transaction.date<=d_to))
                .order_by(Transaction.date)
            )
            transactions = [
                {"id":t.id,"type":str(t.type.value),"amount":t.amount,
                 "date":t.date,"category":None,"description":t.description or "",
                 "receipt_url":t.receipt_url,"receipt_file":t.receipt_file,
                 "is_historical":t.is_historical,"created_at":t.created_at}
                for t in t_r.scalars().all()
            ]
            from app.models import Category, AdCampaign
            cat_r = await db.execute(
                select(Category.name, Category.color, func.sum(Transaction.amount).label("total"))
                .join(Transaction, Transaction.category_id==Category.id)
                .where(and_(Transaction.type==TransactionType.expense,
                            Transaction.date>=d_from, Transaction.date<=d_to))
                .group_by(Category.id, Category.name, Category.color)
                .order_by(func.sum(Transaction.amount).desc())
            )
            exp_by_cat = [{"name":r[0],"color":r[1],"amount":float(r[2])} for r in cat_r.all()]

            ink_r = await db.execute(
                select(InkasRecord, Partner.name)
                .join(Partner, InkasRecord.partner_id==Partner.id)
                .where(and_(InkasRecord.date>=d_from, InkasRecord.date<=d_to))
            )
            inkas = [{"date":r[0].date,"month_label":r[0].month_label,
                      "type":str(r[0].type.value),"partner_name":r[1],
                      "amount":float(r[0].amount)} for r in ink_r.all()]

            ads_r = await db.execute(
                select(AdCampaign)
                .where(and_(AdCampaign.date>=d_from, AdCampaign.date<=d_to))
            )
            ads = [{"date":a.date,"channel_name":a.channel_name,"format":a.format,
                    "amount":a.amount,"subscribers_gained":a.subscribers_gained,
                    "channel_url":a.channel_url,
                    "cost_per_sub": round(a.amount/a.subscribers_gained,2) if a.subscribers_gained else None}
                   for a in ads_r.scalars().all()]

        xlsx = generate_excel_report(
            company_name=company, date_from=d_from, date_to=d_to,
            transactions=transactions, expense_by_category=exp_by_cat,
            inkas_records=inkas, ad_campaigns=ads,
        )
        await call.message.answer_document(
            BufferedInputFile(xlsx, filename=f"report_{d_from}_{d_to}.xlsx"),
            caption=f"📊 {company} — {label}",
        )
        await call.message.delete()
    except Exception as e:
        logger.error(f"Excel error: {e}", exc_info=True)
        await call.message.edit_text(f"❌ Ошибка генерации Excel: {e}",
            reply_markup=back_kb())


# ── Быстрый ввод ──────────────────────────────────────────────────────────────
@dp.message(F.text.regexp(r'^[+\-]\d+'))
async def cmd_quick(message: Message):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, message.from_user.id):
            await message.answer("⛔ Нет доступа"); return
        text = message.text.strip()
        is_inc = text.startswith('+')
        parts = text.lstrip('+-').split(maxsplit=1)
        try: amount = float(parts[0])
        except: return
        desc = parts[1] if len(parts) > 1 else None
        from app.models import AutoTagRule
        cat_id = None
        if desc:
            rules = (await db.execute(select(AutoTagRule))).scalars().all()
            for rule in rules:
                if rule.keyword.lower() in desc.lower():
                    cat_id = rule.category_id; break
        t = Transaction(
            type=TransactionType.income if is_inc else TransactionType.expense,
            amount=amount, date=date.today(), description=desc, category_id=cat_id,
        )
        db.add(t)
        await db.commit()
    emoji = "💚" if is_inc else "❤️"
    await message.answer(
        f"{emoji} <b>{'Доход' if is_inc else 'Расход'} записан</b>\n"
        f"Сумма: <b>{fmt(amount)}</b>"
        + (f"\n{desc}" if desc else ""),
        parse_mode="HTML", reply_markup=main_menu_kb()
    )


# ── Ежедневный отчёт ──────────────────────────────────────────────────────────
async def send_daily(bot: Bot):
    async with AsyncSessionLocal() as db:
        ch = await gs(db, "tg_channel_id")
        if not ch or await gs(db,"notify_daily","true") == "false": return
        today = date.today()
        company = await gs(db,"company_name","Бухгалтерия")
        text = await build_report_text(db, today, today, "Сегодня", company)
        m_kpi = await get_kpi(db, today.replace(day=1), today)
        text += (f"\n\n📅 <b>Месяц итого:</b>\n"
                 f"💚 {fmt(m_kpi['income'])} / ❤️ {fmt(m_kpi['expense'])} / 💰 {fmt(m_kpi['profit'])}")
    try:
        await bot.send_message(ch, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Daily report error: {e}")

async def scheduler(bot: Bot):
    from datetime import timezone, timedelta as td
    MSK = timezone(td(hours=3))
    while True:
        now = datetime.now(MSK)
        target = now.replace(hour=23, minute=0, second=0, microsecond=0)
        if now >= target: target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        await send_daily(bot)

async def main():
    bot = make_bot()
    asyncio.get_event_loop().create_task(scheduler(bot))
    logger.info("Bot started")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
