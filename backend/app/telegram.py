from __future__ import annotations

import asyncio
import fcntl
import hashlib
import html
import logging
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TextIO

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .config import TELEGRAM_BOT_TOKEN
from .language import detect_language
from .pipeline import answer
from .schemas import AskResponse

logger = logging.getLogger("uzex.telegram")
router = Router()
dispatcher = Dispatcher()
dispatcher.include_router(router)
_polling_lock: TextIO | None = None

DEMO_QUESTIONS = [
    "Сколько сделок было заключено в 2024 году?",
    "Какие компании самые активные?",
    "Какие товары лидируют?",
    "Покажи годовой тренд",
]

START_TEXT = (
    "🤖 UZEX AI Analyst\n\n"
    "Assalomu alaykum!\n\n"
    "Men UZEX birja ma'lumotlarini tahlil qiluvchi AI yordamchiman.\n\n"
    "Savol bering:\n"
    "• 2024 yilda nechta bitim bo'lgan?\n"
    "• Eng faol kompaniyalar qaysilar?\n"
    "• Eng katta bitimlar qaysilar?\n\n"
    "Ishonchli ma'lumotlar asosida javob beraman."
)
ANALYZING_TEXT = "🔎 Ma'lumotlar tahlil qilinmoqda..."
ANALYZING_TEXT_RU = "🔎 Анализирую данные..."
ERROR_TEXT_UZ = "❌ So'rovni bajarib bo'lmadi. Iltimos, qayta urinib ko'ring."
ERROR_TEXT_RU = "❌ Не удалось обработать запрос. Попробуйте ещё раз."

MENU_QUESTIONS = {
    "statistics": "2024 yilda nechta bitim tuzilgan?",
    "top_companies": "Eng faol kompaniyalarni ko'rsat",
    "annual_trend": "Yillik savdo trendini ko'rsat",
    "largest_deals": "Eng katta bitimlarni ko'rsat",
    "top_products": "Eng ko'p sotilgan mahsulotlarni ko'rsat",
}
MENU_BUTTONS = (
    ("📊 Statistika", "statistics"),
    ("🏢 Eng faol kompaniyalar", "top_companies"),
    ("📈 Yillik trend", "annual_trend"),
    ("💰 Eng katta bitimlar", "largest_deals"),
    ("🌾 Top mahsulotlar", "top_products"),
)
MENU_CALLBACKS = set(MENU_QUESTIONS)


def format_telegram_answer(result: AskResponse) -> str:
    language = result.language
    if result.rows and not result.verification.passed:
        body = (
            "⚠️ Результат не прошёл проверку, поэтому числа не показываю."
            if language == "ru"
            else "⚠️ Natija tekshiruvdan o'tmadi, shu sababli raqamlar ko'rsatilmaydi."
        )
    elif result.rows and result.intent == "count_deals":
        body = _format_deal_count(result)
    elif result.rows and result.intent == "compare_years" and result.found:
        body = _format_year_comparison(result)
    elif result.rows and result.found:
        body = html.escape(result.answer)
    else:
        body = html.escape(result.answer)

    metadata = []
    if result.sources:
        source_label = "Источник" if language == "ru" else "Manba"
        metadata.append(f"{source_label}: {html.escape(', '.join(result.sources))}")

    if result.verification.passed and result.found:
        verification = "✓ числа подтверждены / raqamlar tasdiqlangan"
    elif result.verification.passed:
        verification = "✓ Проверка выполнена / tekshiruv bajarildi"
    else:
        verification = "⚠️ Проверка не пройдена / tekshiruvdan o'tmadi"

    elapsed = max(0.0, result.execution_ms / 1000)
    confidence = f"{result.confidence:.0%}"
    if language == "ru":
        metadata.append(f"{verification} · уверенность {confidence} · {elapsed:.1f} с")
    else:
        metadata.append(f"{verification} · ishonch {confidence} · {elapsed:.1f} s")
    return body + ("\n\n" + "\n".join(metadata) if metadata else "")


def _format_number(value: object) -> str:
    number = float(value)
    if number.is_integer():
        return f"{int(number):,}".replace(",", " ")
    return f"{number:,.2f}".replace(",", " ")


def _format_period(value: object) -> str:
    return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y")


def _format_deal_count(result: AskResponse) -> str:
    row = result.rows[0]
    language = result.language
    year_match = re.search(r"\b(20\d{2})\b", result.question)
    deals = _format_number(row["deals"])
    year = year_match.group(1) if year_match else None
    period = ""
    if row.get("min_date") and row.get("max_date"):
        period = f"{_format_period(row['min_date'])}–{_format_period(row['max_date'])}"

    lines = []
    if language == "ru":
        title = f"В {year} году заключено <b>{deals}</b> сделок." if year else f"Заключено <b>{deals}</b> сделок."
        lines.extend([title, "", f"• Период: {period}" if period else ""])
        if "deals_not_cancelled" in row and "deals_cancelled" in row:
            lines.append(
                f"• Без аннулированных:\n{_format_number(row['deals_not_cancelled'])} сделок"
            )
            lines.append(
                f"• Аннулированных:\n{_format_number(row['deals_cancelled'])}"
            )
        lines.append(f"• Объём торгов: {_format_amount(row.get('amount_uzs'), language)}")
        if year:
            lines.append(f"• Основание: фильтр year = {year}, учтено {deals} записей.")
    else:
        title = f"{year} yilda <b>{deals} ta</b> bitim tuzilgan." if year else f"<b>{deals} ta</b> bitim tuzilgan."
        lines.extend([title, "", f"• Davr: {period}" if period else ""])
        if "deals_not_cancelled" in row and "deals_cancelled" in row:
            lines.append(
                f"• Bekor qilinmagan: {_format_number(row['deals_not_cancelled'])}; "
                f"bekor qilingan: {_format_number(row['deals_cancelled'])}."
            )
        lines.append(f"• Savdo hajmi: {_format_amount(row.get('amount_uzs'), language)}")
        if year:
            lines.append(f"• Asos: year = {year} filtri, {deals} ta yozuv hisoblandi.")

    return "\n".join(line for line in lines if line is not None)


def _format_amount(value: object, language: str) -> str:
    if value is None:
        return "—"
    amount = float(value)
    if abs(amount) >= 1_000_000_000_000:
        compact = amount / 1_000_000_000_000
        if language == "ru":
            return f"{_format_number(amount)} сум ({compact:.2f} трлн сум)"
        return f"{_format_number(amount)} so'm ({compact:.2f} trln so'm)"
    currency = "сум" if language == "ru" else "so'm"
    return f"{_format_number(amount)} {currency}"


def _format_year_comparison(result: AskResponse) -> str:
    language = result.language
    if language == "ru":
        lines = ["📈 Сделки по годам:"]
        lines.extend(
            f"• {row.get('year')}: <b>{_format_number(row.get('deals', 0))}</b> сделок"
            for row in result.rows
        )
    else:
        lines = ["📈 Yillar bo'yicha bitimlar:"]
        lines.extend(
            f"• {row.get('year')}: <b>{_format_number(row.get('deals', 0))} ta</b> bitim"
            for row in result.rows
        )
    return "\n".join(lines)


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=callback)]
            for label, callback in MENU_BUTTONS
        ]
    )


def _menu_question(callback_data: str) -> str:
    try:
        return MENU_QUESTIONS[callback_data]
    except KeyError as exc:
        raise ValueError("Unknown Telegram menu action") from exc


@dispatcher.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(START_TEXT, reply_markup=menu_keyboard())


@dispatcher.message()
async def answer_question(message: Message) -> None:
    question = (message.text or message.caption or "").strip()
    if not question:
        await message.answer(
            "Savolingizni matn ko'rinishida yuboring yoki menyudan tanlang.",
            reply_markup=menu_keyboard(),
        )
        return

    user_id = message.from_user.id if message.from_user else "unknown"
    logger.info("Question from user_id=%s: %s", user_id, question)
    await _answer_question(message, question, user_id)


@router.callback_query(F.data.in_(MENU_CALLBACKS))
async def handle_menu_callback(callback: CallbackQuery) -> None:
    try:
        await callback.answer()
    except Exception:
        logger.exception("Could not acknowledge callback_id=%s", callback.id)
        return
    if not isinstance(callback.message, Message) or not callback.data:
        return

    question = _menu_question(callback.data)
    user_id = callback.from_user.id
    logger.info("Menu action=%s from user_id=%s: %s", callback.data, user_id, question)
    await _answer_question(callback.message, question, user_id)


async def _answer_question(message: Message, question: str, user_id: int | str) -> None:
    language = detect_language(question)
    try:
        progress_text = ANALYZING_TEXT_RU if language == "ru" else ANALYZING_TEXT
        progress = await message.answer(progress_text)
    except Exception:
        logger.exception("Could not send progress message to user_id=%s", user_id)
        return

    started_at = asyncio.get_running_loop().time()
    try:
        result = await asyncio.to_thread(answer, question)
        elapsed = asyncio.get_running_loop().time() - started_at
        logger.info("Answered user_id=%s in %.3f seconds", user_id, elapsed)
        await progress.edit_text(
            format_telegram_answer(result),
            reply_markup=menu_keyboard(),
        )
    except Exception:
        elapsed = asyncio.get_running_loop().time() - started_at
        logger.exception("Failed to answer user_id=%s after %.3f seconds", user_id, elapsed)
        try:
            error_text = ERROR_TEXT_RU if language == "ru" else ERROR_TEXT_UZ
            await progress.edit_text(error_text, reply_markup=menu_keyboard())
        except Exception:
            logger.exception("Could not send error response to user_id=%s", user_id)


@router.callback_query()
async def reject_unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer("Unknown action", show_alert=False)


def _acquire_polling_lock(token: str):
    lock_name = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    lock_path = Path(tempfile.gettempdir()) / f"uzex-telegram-{lock_name}.lock"
    lock_file = lock_path.open("w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.close()
        raise RuntimeError("Another local polling instance is already running for this bot token") from exc
    return lock_file


async def run_polling() -> None:
    global _polling_lock
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to start the Telegram bot")

    _polling_lock = _acquire_polling_lock(TELEGRAM_BOT_TOKEN)
    bot: Bot | None = None
    try:
        bot = Bot(
            token=TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Removed any existing webhook; starting the single polling process")
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
            close_bot_session=False,
        )
    finally:
        if bot is not None:
            await bot.session.close()
        if _polling_lock is not None:
            fcntl.flock(_polling_lock.fileno(), fcntl.LOCK_UN)
            _polling_lock.close()
            _polling_lock = None