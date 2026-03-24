"""
Сервис уведомлений в Telegram.
Вызывается из API при создании транзакций, инкасов, платежей и т.д.
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def fmt(v: float) -> str:
    return "{:,.0f} ₽".format(v).replace(",", " ")


async def _send_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Отправляет сообщение через Telegram Bot API."""
    try:
        import httpx
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            return r.status_code == 200
    except Exception as e:
        logger.warning(f"TG send failed to {chat_id}: {e}")
        return False


async def notify(
    db,
    event_type: str,       # income | expense | inkas | payment | ad | server
    text: str,             # готовый текст сообщения
) -> None:
    """
    Отправляет уведомление во все активные каналы которые подписаны на event_type.
    Запускается как fire-and-forget задача.
    """
    try:
        from sqlalchemy import select
        from app.models import AppSettings, NotificationChannel

        # Получаем токен бота
        result = await db.execute(
            select(AppSettings).where(AppSettings.key == "tg_bot_token")
        )
        row = result.scalar_one_or_none()
        if not row or not row.value:
            return
        bot_token = row.value

        # Получаем все активные каналы с нужным типом уведомлений
        field_map = {
            "income":  NotificationChannel.notify_income,
            "expense": NotificationChannel.notify_expense,
            "inkas":   NotificationChannel.notify_inkas,
            "payment": NotificationChannel.notify_payment,
            "ad":      NotificationChannel.notify_ad,
            "server":  NotificationChannel.notify_server,
        }
        filter_field = field_map.get(event_type)

        q = select(NotificationChannel).where(NotificationChannel.is_active == True)
        if filter_field is not None:
            q = q.where(filter_field == True)

        ch_result = await db.execute(q)
        channels = ch_result.scalars().all()

        if not channels:
            # Фоллбек: пробуем tg_channel_id из настроек
            ch_result2 = await db.execute(
                select(AppSettings).where(AppSettings.key == "tg_channel_id")
            )
            ch_row = ch_result2.scalar_one_or_none()
            if ch_row and ch_row.value:
                asyncio.ensure_future(_send_message(bot_token, ch_row.value, text))
            return

        for ch in channels:
            asyncio.ensure_future(_send_message(bot_token, ch.chat_id, text))

    except Exception as e:
        logger.warning(f"notify() failed: {e}")


# ── Форматтеры уведомлений ────────────────────────────────────────────────────

def format_transaction(
    action: str,           # "create" | "delete"
    t_type: str,           # "income" | "expense"
    amount: float,
    description: Optional[str],
    category_name: Optional[str],
    date_str: str,
    user_name: str,
    company: str = "Бухгалтерия",
) -> str:
    emoji = "💚" if t_type == "income" else "❤️"
    type_label = "Доход" if t_type == "income" else "Расход"
    action_label = "добавлен" if action == "create" else "удалён"

    lines = [
        f"{emoji} <b>{type_label} {action_label}</b>",
        f"Сумма: <b>{fmt(amount)}</b>",
    ]
    if category_name:
        lines.append(f"Категория: {category_name}")
    if description:
        lines.append(f"Описание: {description}")
    lines.append(f"Дата: {date_str}")
    lines.append(f"Кто: {user_name}")
    lines.append(f"\n<i>{company}</i>")
    return "\n".join(lines)


def format_inkas(
    inkas_type: str,       # "dividend" | "return_inv" | "investment"
    amount: float,
    partner_name: str,
    month_label: Optional[str],
    description: Optional[str],
    user_name: str,
    company: str = "Бухгалтерия",
) -> str:
    type_labels = {
        "dividend":   ("💸", "Дивиденды"),
        "return_inv": ("🔄", "Возврат инвестиций"),
        "investment": ("💼", "Новое вложение"),
    }
    emoji, label = type_labels.get(inkas_type, ("💰", inkas_type))

    lines = [
        f"{emoji} <b>Инкас: {label}</b>",
        f"Партнёр: <b>{partner_name}</b>",
        f"Сумма: <b>{fmt(amount)}</b>",
    ]
    if month_label:
        lines.append(f"Период: {month_label}")
    if description:
        lines.append(f"Описание: {description}")
    lines.append(f"Кто: {user_name}")
    lines.append(f"\n<i>{company}</i>")
    return "\n".join(lines)


def format_payment(
    amount: float,
    plan: Optional[str],
    customer: Optional[str],
    source: Optional[str],
    company: str = "Бухгалтерия",
) -> str:
    lines = [
        f"💳 <b>Новый платёж через API</b>",
        f"Сумма: <b>{fmt(amount)}</b>",
    ]
    if plan:
        lines.append(f"Тариф: {plan}")
    if customer:
        lines.append(f"Клиент: {customer}")
    if source:
        lines.append(f"Источник: {source}")
    lines.append(f"\n<i>{company}</i>")
    return "\n".join(lines)


def format_ad(
    channel_name: str,
    amount: float,
    budget_source: str,
    partner_name: Optional[str],
    user_name: str,
    company: str = "Бухгалтерия",
) -> str:
    source_labels = {
        "account":    "Со счёта",
        "investment": f"Инвестиция ({partner_name or '?'})",
        "stats_only": "Только статистика",
    }
    lines = [
        f"📢 <b>Рекламная кампания</b>",
        f"Канал: {channel_name}",
        f"Бюджет: <b>{fmt(amount)}</b>",
        f"Источник: {source_labels.get(budget_source, budget_source)}",
        f"Кто: {user_name}",
        f"\n<i>{company}</i>",
    ]
    return "\n".join(lines)


def format_conversion(
    campaign_name: str,
    customer_name: Optional[str],
    username: Optional[str],
    amount: float,
    plan: Optional[str],
    roi: float,
    company: str = "Бухгалтерия",
) -> str:
    lines = [
        f"🎯 <b>Конверсия UTM!</b>",
        f"Кампания: {campaign_name}",
        f"Клиент: @{username or '—'} ({customer_name or '—'})",
        f"Сумма: <b>{fmt(amount)}</b>",
    ]
    if plan:
        lines.append(f"Тариф: {plan}")
    if roi != 0:
        sign = "+" if roi > 0 else ""
        lines.append(f"ROI кампании: <b>{sign}{roi}%</b>")
    lines.append(f"\n<i>{company}</i>")
    return "\n".join(lines)
