import asyncio
import logging
import os
import sys
from datetime import date, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

sys.path.insert(0, '/app')
from app.database import AsyncSessionLocal
from app.models import Transaction, TransactionType, Partner, InkasRecord, InkasType, AppSettings, AdCampaign
from sqlalchemy import select, func, and_
from app.services.report_service import generate_pdf_report, generate_excel_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_setting(db, key, default=None):
    r = await db.execute(select(AppSettings).where(AppSettings.key == key))
    row = r.scalar_one_or_none()
    return row.value if row else default


async def get_kpi(db, date_from: date, date_to: date):
    r = await db.execute(
        select(Transaction.type, func.sum(Transaction.amount))
        .where(and_(Transaction.date >= date_from, Transaction.date <= date_to))
        .group_by(Transaction.type)
    )
    rows = r.all()
    income = sum(float(row[1]) for row in rows if row[0] == TransactionType.income)
    expense = sum(float(row[1]) for row in rows if row[0] == TransactionType.expense)
    return income, expense, income - expense


def fmt(v: float) -> str:
    return f"{v:,.0f} ₽".replace(",", " ")


def make_bot() -> Bot:
    token = os.getenv("TG_BOT_TOKEN", "")
    if not token:
        raise ValueError("TG_BOT_TOKEN не задан")
    return Bot(token=token)


dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>Бухгалтерия Bot</b>\n\n"
        "Доступные команды:\n"
        "/today — отчёт за сегодня\n"
        "/week — отчёт за неделю\n"
        "/month — отчёт за месяц\n"
        "/balance — текущий остаток\n"
        "/report — PDF за текущий месяц\n"
        "/excel — Excel за текущий месяц",
        parse_mode="HTML"
    )


@dp.message(Command("today"))
async def cmd_today(message: Message):
    async with AsyncSessionLocal() as db:
        today = date.today()
        income, expense, profit = await get_kpi(db, today, today)
        company = await get_setting(db, "company_name", "Бухгалтерия")

    text = (
        f"📊 <b>{company} — {today.strftime('%d.%m.%Y')}</b>\n\n"
        f"💚 Доход:   <b>{fmt(income)}</b>\n"
        f"❤️ Расход:  <b>{fmt(expense)}</b>\n"
        f"💰 Прибыль: <b>{fmt(profit)}</b>"
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("week"))
async def cmd_week(message: Message):
    async with AsyncSessionLocal() as db:
        today = date.today()
        week_start = today - timedelta(days=6)
        income, expense, profit = await get_kpi(db, week_start, today)
        company = await get_setting(db, "company_name", "Бухгалтерия")

    text = (
        f"📊 <b>{company} — Неделя</b>\n"
        f"{week_start.strftime('%d.%m')} — {today.strftime('%d.%m.%Y')}\n\n"
        f"💚 Доход:   <b>{fmt(income)}</b>\n"
        f"❤️ Расход:  <b>{fmt(expense)}</b>\n"
        f"💰 Прибыль: <b>{fmt(profit)}</b>"
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("month"))
async def cmd_month(message: Message):
    async with AsyncSessionLocal() as db:
        today = date.today()
        month_start = today.replace(day=1)
        income, expense, profit = await get_kpi(db, month_start, today)
        company = await get_setting(db, "company_name", "Бухгалтерия")

    text = (
        f"📊 <b>{company} — {today.strftime('%B %Y')}</b>\n\n"
        f"💚 Доход:   <b>{fmt(income)}</b>\n"
        f"❤️ Расход:  <b>{fmt(expense)}</b>\n"
        f"💰 Прибыль: <b>{fmt(profit)}</b>\n"
        f"📈 В день:  <b>{fmt(income / today.day)}</b>"
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    async with AsyncSessionLocal() as db:
        starting = float(await get_setting(db, "starting_balance", "0") or 0)
        all_inc_r = await db.execute(select(func.sum(Transaction.amount)).where(Transaction.type == TransactionType.income))
        all_exp_r = await db.execute(select(func.sum(Transaction.amount)).where(Transaction.type == TransactionType.expense))
        all_ink_r = await db.execute(
            select(func.sum(InkasRecord.amount)).where(InkasRecord.type.in_([InkasType.dividend, InkasType.return_inv]))
        )
        income = float(all_inc_r.scalar() or 0)
        expense = float(all_exp_r.scalar() or 0)
        inkas = float(all_ink_r.scalar() or 0)
        balance = starting + income - expense - inkas

    await message.answer(f"💳 <b>Остаток на счёте: {fmt(balance)}</b>", parse_mode="HTML")


@dp.message(Command("report"))
async def cmd_report(message: Message):
    await message.answer("⏳ Генерирую PDF отчёт...")
    async with AsyncSessionLocal() as db:
        today = date.today()
        month_start = today.replace(day=1)
        income, expense, profit = await get_kpi(db, month_start, today)
        company = await get_setting(db, "company_name", "Бухгалтерия")

        # Расходы по категориям
        from app.models import Category
        cat_r = await db.execute(
            select(Category.name, Category.color, func.sum(Transaction.amount).label("total"))
            .join(Transaction, Transaction.category_id == Category.id)
            .where(and_(
                Transaction.type == TransactionType.expense,
                Transaction.date >= month_start,
                Transaction.date <= today,
            ))
            .group_by(Category.id, Category.name, Category.color)
            .order_by(func.sum(Transaction.amount).desc())
        )
        expense_by_cat = [{"name": r[0], "color": r[1], "amount": float(r[2])} for r in cat_r.all()]

        partners_r = await db.execute(select(Partner).where(Partner.is_active == True))
        partners_summary = [{"name": p.name, "role_label": p.role_label, "last_dividend": None, "remaining_debt": 0} for p in partners_r.scalars().all()]

    days = today.day
    kpi = {"income": income, "expense": expense, "profit": profit, "avg_per_day": income / days if days > 0 else 0}
    period = f"{month_start.strftime('%d.%m.%Y')} — {today.strftime('%d.%m.%Y')}"

    pdf = generate_pdf_report(
        company_name=company,
        period_label=period,
        kpi=kpi,
        transactions=[],
        expense_by_category=expense_by_cat,
        partners_summary=partners_summary,
    )

    filename = f"report_{today.strftime('%Y_%m')}.pdf"
    await message.answer_document(
        BufferedInputFile(pdf, filename=filename),
        caption=f"📎 Отчёт за {today.strftime('%B %Y')}"
    )


@dp.message(Command("excel"))
async def cmd_excel(message: Message):
    await message.answer("⏳ Генерирую Excel...")
    async with AsyncSessionLocal() as db:
        today = date.today()
        month_start = today.replace(day=1)
        company = await get_setting(db, "company_name", "Бухгалтерия")

        t_r = await db.execute(
            select(Transaction)
            .where(and_(Transaction.date >= month_start, Transaction.date <= today))
            .order_by(Transaction.date)
        )
        transactions = [
            {"id": t.id, "type": str(t.type.value), "amount": t.amount, "date": t.date,
             "category": None, "description": t.description or "", "receipt_url": t.receipt_url,
             "receipt_file": t.receipt_file, "is_historical": t.is_historical, "created_at": t.created_at}
            for t in t_r.scalars().all()
        ]

        from app.models import Category
        cat_r = await db.execute(
            select(Category.name, Category.color, func.sum(Transaction.amount).label("total"))
            .join(Transaction, Transaction.category_id == Category.id)
            .where(and_(Transaction.type == TransactionType.expense, Transaction.date >= month_start, Transaction.date <= today))
            .group_by(Category.id, Category.name, Category.color)
            .order_by(func.sum(Transaction.amount).desc())
        )
        expense_by_cat = [{"name": r[0], "color": r[1], "amount": float(r[2])} for r in cat_r.all()]

    xlsx = generate_excel_report(
        company_name=company, date_from=month_start, date_to=today,
        transactions=transactions, expense_by_category=expense_by_cat,
        inkas_records=[], ad_campaigns=[],
    )
    filename = f"report_{today.strftime('%Y_%m')}.xlsx"
    await message.answer_document(
        BufferedInputFile(xlsx, filename=filename),
        caption=f"📊 Excel отчёт за {today.strftime('%B %Y')}"
    )


# Быстрый ввод: "+15000 доход" или "-9500 реклама"
@dp.message(F.text.regexp(r'^[+\-]\d+'))
async def cmd_quick_entry(message: Message):
    text = message.text.strip()
    is_income = text.startswith('+')
    parts = text.lstrip('+-').split(maxsplit=1)
    try:
        amount = float(parts[0])
    except ValueError:
        return
    description = parts[1] if len(parts) > 1 else None

    async with AsyncSessionLocal() as db:
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
    type_label = "Доход" if is_income else "Расход"
    await message.answer(
        f"{emoji} <b>{type_label} записан</b>\n"
        f"Сумма: <b>{fmt(amount)}</b>\n"
        f"{f'Описание: {description}' if description else ''}",
        parse_mode="HTML"
    )


async def send_daily_report(bot: Bot, channel_id: str, company: str):
    """Ежедневный отчёт в канал"""
    async with AsyncSessionLocal() as db:
        today = date.today()
        income, expense, profit = await get_kpi(db, today, today)
        month_start = today.replace(day=1)
        m_income, m_expense, m_profit = await get_kpi(db, month_start, today)

    text = (
        f"📊 <b>Ежедневный отчёт — {today.strftime('%d.%m.%Y')}</b>\n"
        f"<b>{company}</b>\n\n"
        f"<b>За сегодня:</b>\n"
        f"💚 Доход: {fmt(income)}\n"
        f"❤️ Расход: {fmt(expense)}\n"
        f"💰 Прибыль: {fmt(profit)}\n\n"
        f"<b>За месяц:</b>\n"
        f"💚 Доход: {fmt(m_income)}\n"
        f"❤️ Расход: {fmt(m_expense)}\n"
        f"💰 Прибыль: {fmt(m_profit)}"
    )
    await bot.send_message(channel_id, text, parse_mode="HTML")


async def scheduler(bot: Bot):
    """Планировщик: ежедневный отчёт в 23:00 МСК"""
    import asyncio
    from datetime import datetime, timezone, timedelta as td

    MSK = timezone(td(hours=3))
    while True:
        now = datetime.now(MSK)
        target = now.replace(hour=23, minute=0, second=0, microsecond=0)
        if now >= target:
            target += td(days=1)
        wait = (target - now).total_seconds()
        await asyncio.sleep(wait)

        async with AsyncSessionLocal() as db:
            channel_id = await get_setting(db, "tg_channel_id")
            company = await get_setting(db, "company_name", "Бухгалтерия")
            notify_daily = await get_setting(db, "notify_daily", "true")

        if channel_id and notify_daily != "false":
            try:
                await send_daily_report(bot, channel_id, company)
            except Exception as e:
                logger.error(f"Ошибка отправки ежедневного отчёта: {e}")


async def main():
    bot = make_bot()
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler(bot))
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
