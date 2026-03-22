"""
Buhgalteria Telegram Bot — aiogram 3
Белый список, inline меню, расширенные отчёты, PDF/Excel с выбором периода
"""
import asyncio
import logging
import os
import sys
from datetime import date, timedelta, datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ── DB helpers ────────────────────────────────────────────────────────────────
from app.database import AsyncSessionLocal
from app.models import (
    Transaction, TransactionType, Partner, InkasRecord, InkasType,
    AppSettings, Payment, User,
)
from sqlalchemy import select, func, and_
from app.services.report_service import generate_pdf_report, generate_excel_report


async def get_setting(db, key: str, default=None) -> Optional[str]:
    r = await db.execute(select(AppSettings).where(AppSettings.key == key))
    row = r.scalar_one_or_none()
    return row.value if row else default


async def get_allowed_ids(db) -> list[int]:
    """Белый список Telegram ID из настроек."""
    raw = await get_setting(db, "tg_allowed_ids", "")
    if not raw:
        # Фоллбек — только admin из tg_admin_id
        admin = await get_setting(db, "tg_admin_id", "")
        return [int(admin)] if admin and admin.isdigit() else []
    ids = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def fmt(v: float) -> str:
    return "{:,.0f} ₽".format(v).replace(",", " ")


async def check_access(db, user_id: int) -> bool:
    allowed = await get_allowed_ids(db)
    if not allowed:
        return True  # если список пуст — пускаем всех
    return user_id in allowed


# ── KPI helper ────────────────────────────────────────────────────────────────
async def get_kpi(db, date_from: date, date_to: date) -> dict:
    r = await db.execute(
        select(Transaction.type, func.sum(Transaction.amount))
        .where(and_(Transaction.date >= date_from, Transaction.date <= date_to))
        .group_by(Transaction.type)
    )
    rows = r.all()
    income  = float(sum(row[1] for row in rows if row[0] == TransactionType.income) or 0)
    expense = float(sum(row[1] for row in rows if row[0] == TransactionType.expense) or 0)
    return {"income": income, "expense": expense, "profit": income - expense}


async def get_inkas_summary(db, date_from: date, date_to: date) -> list[dict]:
    """Инкас за период с именами партнёров."""
    r = await db.execute(
        select(InkasRecord, Partner.name)
        .join(Partner, InkasRecord.partner_id == Partner.id)
        .where(and_(InkasRecord.date >= date_from, InkasRecord.date <= date_to))
        .order_by(InkasRecord.date.desc())
    )
    rows = r.all()
    type_labels = {"dividend": "ДВД", "return_inv": "Возврат", "investment": "Вложение"}
    return [
        {
            "partner": row[1],
            "type": type_labels.get(str(row[0].type.value), str(row[0].type.value)),
            "amount": float(row[0].amount),
            "month_label": row[0].month_label or "",
        }
        for row in rows
    ]


async def get_partner_debts(db) -> list[dict]:
    """Текущие долги перед партнёрами."""
    partners_r = await db.execute(select(Partner).where(Partner.is_active == True))
    partners = partners_r.scalars().all()
    debts = []
    for p in partners:
        total_inv = p.initial_investment
        total_ret = p.initial_returned
        inv_r = await db.execute(
            select(func.sum(InkasRecord.amount))
            .where(and_(InkasRecord.partner_id == p.id, InkasRecord.type == InkasType.investment))
        )
        ret_r = await db.execute(
            select(func.sum(InkasRecord.amount))
            .where(and_(InkasRecord.partner_id == p.id, InkasRecord.type == InkasType.return_inv))
        )
        total_inv += float(inv_r.scalar() or 0)
        total_ret += float(ret_r.scalar() or 0)
        debt = max(0.0, total_inv - total_ret)
        if debt > 0 or total_inv > 0:
            debts.append({"name": p.name, "debt": debt, "invested": total_inv, "returned": total_ret})
    return debts


async def build_report_text(db, date_from: date, date_to: date, label: str, company: str) -> str:
    kpi = await get_kpi(db, date_from, date_to)
    inkas = await get_inkas_summary(db, date_from, date_to)
    debts = await get_partner_debts(db)
    days = (date_to - date_from).days + 1

    lines = [
        f"📊 <b>{company}</b>",
        f"📅 <b>{label}</b>",
        f"({date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')})",
        "",
        "━━━━━━━━━━━━━━━━━━",
        f"💚 Доход:   <b>{fmt(kpi['income'])}</b>",
        f"❤️ Расход:  <b>{fmt(kpi['expense'])}</b>",
        f"💰 Прибыль: <b>{fmt(kpi['profit'])}</b>",
    ]
    if days > 1:
        lines.append(f"📈 В день:  <b>{fmt(kpi['income'] / days)}</b>")

    if inkas:
        lines += ["", "━━━━━━━━━━━━━━━━━━", "💸 <b>Инкас за период:</b>"]
        for rec in inkas[:8]:
            lines.append(f"  • {rec['partner']} — {rec['type']}: {fmt(rec['amount'])}" +
                         (f" ({rec['month_label']})" if rec['month_label'] else ""))

    if debts:
        lines += ["", "━━━━━━━━━━━━━━━━━━", "🏦 <b>Долги перед партнёрами:</b>"]
        for d in debts:
            if d['debt'] > 0:
                lines.append(f"  • {d['name']}: осталось <b>{fmt(d['debt'])}</b>")
            else:
                lines.append(f"  • {d['name']}: ✅ погашено")

    lines += ["", f"<i>Buhgalteria Bot</i>"]
    return "\n".join(lines)


# ── Keyboards ─────────────────────────────────────────────────────────────────
def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📊 Отчёт", callback_data="menu:report"),
        InlineKeyboardButton(text="💳 Платежи", callback_data="menu:payments"),
    )
    kb.row(
        InlineKeyboardButton(text="💰 Баланс", callback_data="menu:balance"),
        InlineKeyboardButton(text="🏦 Партнёры", callback_data="menu:partners"),
    )
    kb.row(
        InlineKeyboardButton(text="📄 PDF отчёт", callback_data="menu:pdf"),
        InlineKeyboardButton(text="📊 Excel отчёт", callback_data="menu:excel"),
    )
    return kb.as_markup()


def period_kb(prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📅 Сегодня",  callback_data=f"{prefix}:today"),
        InlineKeyboardButton(text="📅 Неделя",   callback_data=f"{prefix}:week"),
    )
    kb.row(
        InlineKeyboardButton(text="📅 Месяц",    callback_data=f"{prefix}:month"),
        InlineKeyboardButton(text="📅 Год",       callback_data=f"{prefix}:year"),
    )
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:back"))
    return kb.as_markup()


def back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:back"))
    return kb.as_markup()


def period_dates(period: str):
    today = date.today()
    if period == "today":
        return today, today, "Сегодня"
    elif period == "week":
        return today - timedelta(days=6), today, "Неделя"
    elif period == "month":
        return today.replace(day=1), today, f"{today.strftime('%B %Y')}"
    elif period == "year":
        return today.replace(month=1, day=1), today, str(today.year)
    return today, today, "Сегодня"


# ── Bot setup ─────────────────────────────────────────────────────────────────
def make_bot() -> Bot:
    token = os.getenv("TG_BOT_TOKEN", "")
    if not token:
        raise ValueError("TG_BOT_TOKEN не задан")
    return Bot(token=token)


dp = Dispatcher()


# ── /start ────────────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: Message):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, message.from_user.id):
            await message.answer("⛔ Доступ запрещён.")
            return
        company = await get_setting(db, "company_name", "Бухгалтерия")

    await message.answer(
        f"👋 <b>{company} — панель управления</b>\n\nВыберите действие:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


# ── Callback: главное меню ────────────────────────────────────────────────────
@dp.callback_query(F.data == "menu:back")
async def cb_back(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id):
            await call.answer("⛔ Нет доступа", show_alert=True)
            return
        company = await get_setting(db, "company_name", "Бухгалтерия")
    await call.message.edit_text(
        f"🏠 <b>{company}</b>\n\nВыберите действие:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "menu:report")
async def cb_report_menu(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
    await call.message.edit_text(
        "📊 <b>Отчёт</b>\nВыберите период:",
        reply_markup=period_kb("report"),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "menu:pdf")
async def cb_pdf_menu(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
    await call.message.edit_text(
        "📄 <b>PDF отчёт</b>\nВыберите период:",
        reply_markup=period_kb("pdf"),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "menu:excel")
async def cb_excel_menu(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
    await call.message.edit_text(
        "📊 <b>Excel отчёт</b>\nВыберите период:",
        reply_markup=period_kb("excel"),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "menu:balance")
async def cb_balance(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        starting = float(await get_setting(db, "starting_balance", "0") or 0)
        all_inc = await db.execute(select(func.sum(Transaction.amount)).where(Transaction.type == TransactionType.income))
        all_exp = await db.execute(select(func.sum(Transaction.amount)).where(Transaction.type == TransactionType.expense))
        all_ink = await db.execute(
            select(func.sum(InkasRecord.amount)).where(
                InkasRecord.type.in_([InkasType.dividend, InkasType.return_inv])
            )
        )
        balance = starting + float(all_inc.scalar() or 0) - float(all_exp.scalar() or 0) - float(all_ink.scalar() or 0)
        company = await get_setting(db, "company_name", "Бухгалтерия")

    await call.message.edit_text(
        f"💳 <b>{company}</b>\n\n"
        f"Остаток на счёте: <b>{fmt(balance)}</b>",
        reply_markup=back_kb(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "menu:partners")
async def cb_partners(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        debts = await get_partner_debts(db)
        company = await get_setting(db, "company_name", "Бухгалтерия")

    lines = [f"🏦 <b>{company} — Партнёры</b>\n"]
    for d in debts:
        status = "✅ погашено" if d['debt'] == 0 else f"долг {fmt(d['debt'])}"
        lines.append(f"👤 <b>{d['name']}</b>")
        lines.append(f"   Вложено: {fmt(d['invested'])}")
        lines.append(f"   Возвращено: {fmt(d['returned'])}")
        lines.append(f"   Статус: {status}\n")

    await call.message.edit_text(
        "\n".join(lines) if lines else "Партнёры не найдены",
        reply_markup=back_kb(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "menu:payments")
async def cb_payments(call: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        today = date.today()
        # Статистика платежей
        total_r = await db.execute(
            select(func.sum(Payment.amount), func.count(Payment.id))
            .where(Payment.date == today)
        )
        today_amt, today_cnt = total_r.one()
        active_r = await db.execute(
            select(func.count(Payment.id)).where(Payment.sub_end >= today)
        )
        expiry_r = await db.execute(
            select(func.count(Payment.id)).where(
                and_(Payment.sub_end >= today, Payment.sub_end <= today + timedelta(days=3))
            )
        )
        # По тегам
        tags_r = await db.execute(
            select(Payment.plan_tag, Payment.plan, func.count(Payment.id))
            .where(Payment.sub_end >= today)
            .group_by(Payment.plan_tag, Payment.plan)
        )
        tags = tags_r.all()
        company = await get_setting(db, "company_name", "Бухгалтерия")

    lines = [
        f"💳 <b>{company} — Платежи</b>",
        "",
        f"📅 Сегодня: <b>{today_cnt or 0}</b> платежей на <b>{fmt(float(today_amt or 0))}</b>",
        f"✅ Активных подписок: <b>{active_r.scalar() or 0}</b>",
        f"⚠️ Истекают через 3 дня: <b>{expiry_r.scalar() or 0}</b>",
    ]
    if tags:
        lines += ["", "📊 <b>По тарифам (активные):</b>"]
        for tag, plan, cnt in tags:
            lines.append(f"  • {plan or tag or '?'}: <b>{cnt}</b>")

    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=back_kb(),
        parse_mode="HTML",
    )


# ── Callback: отчёт за период ─────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("report:"))
async def cb_report(call: CallbackQuery):
    period = call.data.split(":")[1]
    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        date_from, date_to, label = period_dates(period)
        company = await get_setting(db, "company_name", "Бухгалтерия")
        text = await build_report_text(db, date_from, date_to, label, company)

    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")


# ── Callback: PDF ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("pdf:"))
async def cb_pdf(call: CallbackQuery):
    period = call.data.split(":")[1]
    await call.answer("⏳ Генерирую PDF...")
    await call.message.edit_text("⏳ Генерирую PDF отчёт...")

    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        date_from, date_to, label = period_dates(period)
        company = await get_setting(db, "company_name", "Бухгалтерия")
        kpi = await get_kpi(db, date_from, date_to)
        inkas = await get_inkas_summary(db, date_from, date_to)
        debts = await get_partner_debts(db)

        # Расходы по категориям
        from app.models import Category
        cat_r = await db.execute(
            select(Category.name, Category.color, func.sum(Transaction.amount).label("total"))
            .join(Transaction, Transaction.category_id == Category.id)
            .where(and_(Transaction.type == TransactionType.expense,
                        Transaction.date >= date_from, Transaction.date <= date_to))
            .group_by(Category.id, Category.name, Category.color)
            .order_by(func.sum(Transaction.amount).desc())
        )
        expense_by_cat = [{"name": r[0], "color": r[1], "amount": float(r[2])} for r in cat_r.all()]

        # Партнёры для отчёта
        partners_summary = [
            {
                "name": d["name"],
                "role_label": "Партнёр",
                "last_dividend": None,
                "remaining_debt": d["debt"],
            }
            for d in debts
        ]

    days = (date_to - date_from).days + 1
    kpi_data = {**kpi, "avg_per_day": kpi["income"] / days if days > 0 else 0}

    pdf_bytes = generate_pdf_report(
        company_name=company,
        period_label=f"{label}: {date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}",
        kpi=kpi_data,
        transactions=[],
        expense_by_category=expense_by_cat,
        partners_summary=partners_summary,
    )

    from aiogram.types import BufferedInputFile
    await call.message.answer_document(
        BufferedInputFile(pdf_bytes, filename=f"report_{date_from}_{date_to}.pdf"),
        caption=f"📄 {company} — {label}",
    )
    await call.message.delete()


# ── Callback: Excel ───────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("excel:"))
async def cb_excel(call: CallbackQuery):
    period = call.data.split(":")[1]
    await call.answer("⏳ Генерирую Excel...")
    await call.message.edit_text("⏳ Генерирую Excel отчёт...")

    async with AsyncSessionLocal() as db:
        if not await check_access(db, call.from_user.id): return
        date_from, date_to, label = period_dates(period)
        company = await get_setting(db, "company_name", "Бухгалтерия")

        # Транзакции
        t_r = await db.execute(
            select(Transaction)
            .where(and_(Transaction.date >= date_from, Transaction.date <= date_to))
            .order_by(Transaction.date)
        )
        transactions = [
            {"id": t.id, "type": str(t.type.value), "amount": t.amount,
             "date": t.date, "category": None, "description": t.description or "",
             "receipt_url": t.receipt_url, "receipt_file": t.receipt_file,
             "is_historical": t.is_historical, "created_at": t.created_at}
            for t in t_r.scalars().all()
        ]

        from app.models import Category, AdCampaign
        cat_r = await db.execute(
            select(Category.name, Category.color, func.sum(Transaction.amount).label("total"))
            .join(Transaction, Transaction.category_id == Category.id)
            .where(and_(Transaction.type == TransactionType.expense,
                        Transaction.date >= date_from, Transaction.date <= date_to))
            .group_by(Category.id, Category.name, Category.color)
            .order_by(func.sum(Transaction.amount).desc())
        )
        expense_by_cat = [{"name": r[0], "color": r[1], "amount": float(r[2])} for r in cat_r.all()]

        ink_r = await db.execute(
            select(InkasRecord, Partner.name)
            .join(Partner, InkasRecord.partner_id == Partner.id)
            .where(and_(InkasRecord.date >= date_from, InkasRecord.date <= date_to))
        )
        inkas_records = [
            {"date": r[0].date, "month_label": r[0].month_label, "type": str(r[0].type.value),
             "partner_name": r[1], "amount": float(r[0].amount)}
            for r in ink_r.all()
        ]

        ads_r = await db.execute(
            select(AdCampaign).where(and_(
                AdCampaign.date >= date_from, AdCampaign.date <= date_to))
        )
        ad_campaigns = [
            {"date": a.date, "channel_name": a.channel_name, "format": a.format,
             "amount": a.amount, "subscribers_gained": a.subscribers_gained,
             "channel_url": a.channel_url,
             "cost_per_sub": round(a.amount / a.subscribers_gained, 2) if a.subscribers_gained else None}
            for a in ads_r.scalars().all()
        ]

    xlsx = generate_excel_report(
        company_name=company,
        date_from=date_from, date_to=date_to,
        transactions=transactions,
        expense_by_category=expense_by_cat,
        inkas_records=inkas_records,
        ad_campaigns=ad_campaigns,
    )

    from aiogram.types import BufferedInputFile
    await call.message.answer_document(
        BufferedInputFile(xlsx, filename=f"report_{date_from}_{date_to}.xlsx"),
        caption=f"📊 {company} — {label}",
    )
    await call.message.delete()


# ── Быстрый ввод: +15000 реклама ─────────────────────────────────────────────
@dp.message(F.text.regexp(r'^[+\-]\d+'))
async def cmd_quick_entry(message: Message):
    async with AsyncSessionLocal() as db:
        if not await check_access(db, message.from_user.id):
            await message.answer("⛔ Нет доступа")
            return

        text = message.text.strip()
        is_income = text.startswith('+')
        parts = text.lstrip('+-').split(maxsplit=1)
        try:
            amount = float(parts[0])
        except ValueError:
            return
        description = parts[1] if len(parts) > 1 else None

        from app.models import AutoTagRule
        category_id = None
        if description:
            rules_r = await db.execute(select(AutoTagRule))
            for rule in rules_r.scalars().all():
                if rule.keyword.lower() in description.lower():
                    category_id = rule.category_id
                    break

        t = Transaction(
            type=TransactionType.income if is_income else TransactionType.expense,
            amount=amount,
            date=date.today(),
            description=description,
            category_id=category_id,
        )
        db.add(t)
        await db.commit()

    emoji = "💚" if is_income else "❤️"
    label = "Доход" if is_income else "Расход"
    await message.answer(
        f"{emoji} <b>{label} записан</b>\n"
        f"Сумма: <b>{fmt(amount)}</b>"
        + (f"\nОписание: {description}" if description else ""),
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


# ── Планировщик: ежедневный отчёт ────────────────────────────────────────────
async def send_daily_report(bot: Bot):
    async with AsyncSessionLocal() as db:
        channel_id = await get_setting(db, "tg_channel_id")
        notify_daily = await get_setting(db, "notify_daily", "true")
        if not channel_id or notify_daily == "false":
            return
        today = date.today()
        month_start = today.replace(day=1)
        company = await get_setting(db, "company_name", "Бухгалтерия")
        text = await build_report_text(db, today, today, "Сегодня", company)
        # Добавляем итог за месяц
        m_kpi = await get_kpi(db, month_start, today)
        text += f"\n\n📅 <b>Итого за месяц:</b>\n💚 {fmt(m_kpi['income'])} / ❤️ {fmt(m_kpi['expense'])} / 💰 {fmt(m_kpi['profit'])}"

    try:
        await bot.send_message(channel_id, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Daily report error: {e}")


async def scheduler(bot: Bot):
    from datetime import timezone, timedelta as td
    MSK = timezone(td(hours=3))
    while True:
        now = datetime.now(MSK)
        target = now.replace(hour=23, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        await send_daily_report(bot)


async def main():
    bot = make_bot()
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler(bot))
    logger.info("Bot started")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
