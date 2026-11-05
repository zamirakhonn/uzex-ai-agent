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
from .schemas import AskResponse, Language

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
DEMO_QUESTIONS_UZ = [
    "2024 yilda nechta bitim bo'lgan?",
    "Eng faol kompaniyalar qaysilar?",
    "Qaysi mahsulotlar yetakchi?",
    "Yillik savdo trendi qanday?",
]

START_TEXT = (
    "🤖 UZEX AI Analyst\n\n"
    "Assalomu alaykum!\n\n"
    "Men UZEX birja ma'lumotlarini tahlil qiluvchi AI yordamchiman.\n\n"
    "Savol bering:\n"
    "📊 2024 yilda nechta bitim bo'lgan?\n"
    "🏢 Eng faol kompaniyalar qaysilar?\n"
    "💰 Eng katta bitimlar qaysilar?\n"
    "📈 Yillik savdo trendi qanday?\n"
    "🌾 Eng ko'p sotilgan mahsulotlar qaysilar?\n\n"
    "Ishonchli ma'lumotlar asosida javob beraman."
)
START_TEXT_RU = (
    "🤖 UZEX AI Analyst\n\n"
    "Здравствуйте!\n\n"
    "Я AI-помощник по анализу данных Узбекской республиканской товарно-сырьевой биржи.\n\n"
    "Спросите, например:\n"
    "📊 сколько сделок было в 2024 году?\n"
    "🏢 какие компании самые активные?\n"
    "💰 какие сделки самые крупные?\n"
    "📈 как менялся годовой тренд?\n"
    "🌾 какие товары лидируют?\n\n"
    "Отвечаю на основе проверенных данных."
)
ANALYZING_TEXT = "🔎 Ma'lumotlar tahlil qilinmoqda..."
ANALYZING_TEXT_RU = "🔎 Анализирую данные..."
ERROR_TEXT_UZ = "❌ So'rovni bajarib bo'lmadi. Iltimos, qayta urinib ko'ring."
ERROR_TEXT_RU = "❌ Не удалось обработать запрос. Попробуйте ещё раз."

MENU_QUESTIONS: dict[str, dict[Language, str]] = {
    "statistics": {
        "uz": "2024 yilda nechta bitim bo'lgan?",
        "ru": "Сколько сделок было заключено в 2024 году?",
    },
    "top_companies": {
        "uz": "Eng faol kompaniyalarni ko'rsat",
        "ru": "Какие компании самые активные?",
    },
    "annual_trend": {
        "uz": "Yillik savdo trendini ko'rsat",
        "ru": "Сравните сделки за 2024 и 2025 годы",
    },
    "largest_deals": {
        "uz": "Eng katta bitimlarni ko'rsat",
        "ru": "Какая самая крупная сделка?",
    },
    "top_products": {
        "uz": "Eng ko'p sotilgan mahsulotlar qaysilar?",
        "ru": "Какие товары лидируют?",
    },
}
MENU_CALLBACKS = set(MENU_QUESTIONS)
LANGUAGE_LABELS = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский"}
_user_languages: dict[int, Language] = {}
_last_results: dict[int, AskResponse] = {}


def format_telegram_answer(result: AskResponse) -> str:
    language = result.language
    has_rows = bool(result.rows)
    if has_rows and not result.verification.passed:
        conclusion = (
            "⚠️ Результат не прошёл проверку, поэтому числовой ответ не показываю."
            if language == "ru"
            else "⚠️ Natija tekshiruvdan o'tmadi, shuning uchun raqamlarni ko'rsatmayman."
        )
        details = []
        insight = None
    elif not result.found:
        conclusion = (
            "По имеющимся данным ответ не найден."
            if language == "ru"
            else "Mavjud ma'lumotlar asosida javob topilmadi."
        )
        details = []
        insight = None
    elif has_rows:
        conclusion, details, insight = _format_result_details(result)
    else:
        conclusion = html.escape(result.answer)
        details = []
        insight = None

    sections = [conclusion]
    if details:
        sections.extend(["", "• " + "\n\n• ".join(details)])
    if insight:
        sections.extend(["", html.escape(insight)])

    source_lines = _format_source(result)
    if source_lines:
        source_heading = "Основание:" if language == "ru" else "Asos:"
        sections.extend(["", source_heading, *source_lines])

    if result.verification.passed and has_rows:
        verification = "✓ числа подтверждены" if language == "ru" else "✓ raqamlar tasdiqlangan"
    elif result.verification.passed:
        verification = "✓ Проверка выполнена" if language == "ru" else "✓ Tekshiruv bajarildi"
    else:
        verification = "⚠️ Проверка не пройдена" if language == "ru" else "⚠️ Tekshiruvdan o'tmadi"

    elapsed = max(0.0, result.execution_ms / 1000)
    sections.extend(["", f"{verification} · {elapsed:.1f} {'с' if language == 'ru' else 's'}"])

    if result.sql and _wants_sql(result.question):
        sections.extend(["", "run_sql", f"<pre>{html.escape(result.sql.strip())}</pre>"])
    return "\n".join(sections)


def _format_result_details(result: AskResponse) -> tuple[str, list[str], str | None]:
    language = result.language
    row = result.rows[0]

    if result.intent == "count_deals":
        return _format_deal_count(result)

    if result.intent == "compare_years":
        lines = [
            f"{item.get('year')}: {_format_number(item.get('deals', 0))}"
            for item in result.rows
        ]
        if language == "ru":
            return "Сравнение числа сделок:", lines, None
        return "Bitimlar soni taqqoslanishi:", lines, None

    if result.intent == "top_company":
        name = html.escape(str(row.get("name") or ""))
        deals = _format_number(row.get("deals", 0))
        inn = html.escape(str(row.get("inn") or "—"))
        amount = _format_amount(row.get("amount_uzs"), language)
        if language == "ru":
            conclusion = f"Самая активная компания — <b>{name}</b>."
            lines = [
                f"ИНН: {inn}",
                f"Общая сумма: <b>{amount}</b>",
                f"Количество сделок: <b>{deals}</b>",
            ]
            if len(result.rows) > 1:
                heading = "Следующие TOP компании:"
        else:
            conclusion = f"Eng faol kompaniya — <b>{name}</b>."
            lines = [
                f"STIR: {inn}",
                f"Jami summa: <b>{amount}</b>",
                f"Bitimlar soni: <b>{deals} ta</b>",
            ]
            if len(result.rows) > 1:
                heading = "Keyingi TOP kompaniyalar:"
        if len(result.rows) > 1:
            ranked = []
            for index, item in enumerate(result.rows[1:4], start=2):
                item_name = html.escape(str(item.get("name") or ""))
                item_deals = _format_number(item.get("deals", 0))
                ranked.append(f"{index}. <b>{item_name}</b> — {item_deals}")
            lines.append(heading + "\n" + "\n".join(ranked))
        return conclusion, lines, None

    if result.intent == "top_product":
        product = html.escape(str(row.get("product") or ""))
        deals = _format_number(row.get("deals", 0))
        conclusion = (
            f"Лидирующий товар — <b>{product}</b>: <b>{deals}</b> сделок."
            if language == "ru"
            else f"Yetakchi mahsulot — <b>{product}</b>: <b>{deals} ta</b> bitim."
        )
        label = "Топ товаров" if language == "ru" else "Top mahsulotlar"
        lines = [label + ":"]
        ranked = []
        for index, item in enumerate(result.rows[:5], start=1):
            item_name = html.escape(str(item.get("product") or ""))
            item_deals = _format_number(item.get("deals", 0))
            ranked.append(f"{index}. <b>{item_name}</b> — {item_deals}")
        if ranked:
            lines = [label + ":\n" + "\n".join(ranked)]
        return conclusion, lines, None

    if result.intent == "company_deals":
        name = html.escape(str(row.get("name") or ""))
        deals = _format_number(row.get("deals", 0))
        if language == "ru":
            conclusion = f"По компании <b>{name}</b> учтено <b>{deals}</b> сделок."
            details = [f"ИНН: {html.escape(str(row.get('inn') or '—'))}"]
            details.append(
                f"Роль: продавец — {_format_number(row.get('as_seller', 0))}; "
                f"покупатель — {_format_number(row.get('as_buyer', 0))}"
            )
            amount_label = "Объём торгов"
        else:
            conclusion = f"<b>{name}</b> bo'yicha <b>{deals} ta</b> bitim qayd etilgan."
            details = [f"STIR: {html.escape(str(row.get('inn') or '—'))}"]
            details.append(
                f"Roli: sotuvchi — {_format_number(row.get('as_seller', 0))}; "
                f"xaridor — {_format_number(row.get('as_buyer', 0))}"
            )
            amount_label = "Savdo hajmi"
        if row.get("amount_uzs") is not None:
            details.append(f"{amount_label}: {_format_amount(row['amount_uzs'], language)}")
        return conclusion, details, None

    if result.intent in {"max_deal", "min_deal", "deal_lookup"}:
        product = html.escape(str(row.get("product_name") or ""))
        deal_id = _format_number(row.get("deal_id")) if row.get("deal_id") is not None else None
        amount = _format_amount(row.get("amount_uzs"), language)
        if language == "ru":
            if result.intent == "max_deal":
                conclusion = f"Крупнейшая сделка — <b>{product}</b>: <b>{amount}</b>."
            elif result.intent == "min_deal":
                conclusion = f"Наименьшая сделка — <b>{product}</b>: <b>{amount}</b>."
            else:
                conclusion = f"Сделка №{deal_id}: <b>{product}</b>, сумма <b>{amount}</b>."
            details = []
            details.append(f"Дата: {_format_period(row['deal_date'])}" if row.get("deal_date") else "")
            if row.get("seller_name"):
                details.append(f"Продавец: {html.escape(str(row['seller_name']))}")
                if row.get("seller_inn"):
                    details.append(f"ИНН: {html.escape(str(row['seller_inn']))}")
            if row.get("buyer_name"):
                details.append(f"Покупатель: {html.escape(str(row['buyer_name']))}")
                if row.get("buyer_inn"):
                    details.append(f"ИНН: {html.escape(str(row['buyer_inn']))}")
            if row.get("status"):
                details.append(f"Статус: {html.escape(str(row['status']))}")
        else:
            if result.intent == "max_deal":
                conclusion = f"Eng yirik bitim — <b>{product}</b>: <b>{amount}</b>."
            elif result.intent == "min_deal":
                conclusion = f"Eng kichik bitim — <b>{product}</b>: <b>{amount}</b>."
            else:
                conclusion = f"Bitim №{deal_id}: <b>{product}</b>, summa <b>{amount}</b>."
            details = []
            details.append(f"Sana: {_format_period(row['deal_date'])}" if row.get("deal_date") else "")
            if row.get("seller_name"):
                details.append(f"Sotuvchi: {html.escape(str(row['seller_name']))}")
                if row.get("seller_inn"):
                    details.append(f"STIR: {html.escape(str(row['seller_inn']))}")
            if row.get("buyer_name"):
                details.append(f"Xaridor: {html.escape(str(row['buyer_name']))}")
                if row.get("buyer_inn"):
                    details.append(f"STIR: {html.escape(str(row['buyer_inn']))}")
            if row.get("status"):
                details.append(f"Holat: {html.escape(str(row['status']))}")
        return conclusion, [detail for detail in details if detail], None

    evidence = [
        f"{html.escape(item.label)}: {html.escape(item.value)}"
        for item in result.evidence
    ]
    return html.escape(result.answer), evidence, None


def _format_source(result: AskResponse) -> list[str]:
    sources = list(result.sources)
    if not sources and result.sql:
        known_tables = ("deals_enriched", "participants", "contracts", "brokers", "usd_rates")
        lowered_sql = result.sql.lower()
        sources = [table for table in known_tables if re.search(rf"\b(?:from|join)\s+{table}\b", lowered_sql)]
    source_labels = {
        "deals_*.csv": "таблица deals" if result.language == "ru" else "deals jadvali",
        "deals_enriched": "таблица deals" if result.language == "ru" else "deals jadvali",
        "deals": "таблица deals" if result.language == "ru" else "deals jadvali",
        "participants.csv": "таблица participants" if result.language == "ru" else "participants jadvali",
        "contracts.csv": "таблица contracts" if result.language == "ru" else "contracts jadvali",
        "brokers.csv": "таблица brokers" if result.language == "ru" else "brokers jadvali",
        "usd_rates.csv": "таблица usd_rates" if result.language == "ru" else "usd_rates jadvali",
    }
    lines = [html.escape(source_labels.get(source, source)) for source in sources]

    year_match = re.search(r"\b(20\d{2})\b", result.question)
    if year_match and result.sql and re.search(r"\byear\s*=\s*\?", result.sql, re.I):
        lines.append(f"year={year_match.group(1)}" if result.language == "ru" else f"year={year_match.group(1)} filtri")

    if result.rows and "deals" in result.rows[0]:
        count = _format_number(result.rows[0]["deals"])
        lines.append(f"{count} записей" if result.language == "ru" else f"{count} ta yozuv")
    return lines


def _format_basis(result: AskResponse) -> str:
    language = result.language
    if language == "ru":
        heading = "📄 Основание"
        source_label = "Источник"
        filter_label = "Фильтр"
        calculation_label = "Расчёт"
        no_query = "SQL-запрос недоступен."
    else:
        heading = "📄 Hisoblash asosi"
        source_label = "Manba"
        filter_label = "Filtr"
        calculation_label = "Hisoblash"
        no_query = "SQL so'rovi mavjud emas."

    lines = [heading]
    sources = _format_source(result)
    if sources:
        lines.extend(["", f"{source_label}:", *sources])

    year_match = re.search(r"\b(20\d{2})\b", result.question)
    if year_match:
        lines.extend(["", f"{filter_label}: year={year_match.group(1)}"])
    else:
        lines.extend(["", f"{filter_label}: {html.escape(result.question)}"])

    calculation = {
        "count_deals": "COUNT(*) по сделкам с выбранным фильтром" if language == "ru" else "Tanlangan filtr bo'yicha COUNT(*)",
        "top_company": "Группировка по компаниям и сортировка по числу сделок" if language == "ru" else "Kompaniyalarni guruhlash va bitimlar soni bo'yicha saralash",
        "company_deals": "Подсчёт сделок и суммы по компании" if language == "ru" else "Kompaniya bo'yicha bitimlar soni va summasi",
        "top_product": "Группировка сделок по товарам" if language == "ru" else "Bitimlarni mahsulotlar bo'yicha guruhlash",
        "max_deal": "Сортировка по сумме сделки по убыванию" if language == "ru" else "Bitim summasini kamayish tartibida saralash",
        "min_deal": "Сортировка по сумме сделки по возрастанию" if language == "ru" else "Bitim summasini o'sish tartibida saralash",
        "compare_years": "Подсчёт сделок отдельно по каждому году" if language == "ru" else "Har bir yil bo'yicha bitimlarni alohida hisoblash",
    }.get(result.intent)
    if calculation:
        lines.extend(["", f"{calculation_label}: {calculation}"])

    if result.sql:
        lines.extend(["", "<pre>", html.escape(result.sql.strip()), "</pre>"])
    else:
        lines.extend(["", no_query])
    return "\n".join(lines)


def _format_number(value: object) -> str:
    if value is None:
        return "—"
    number = float(value)
    if number.is_integer():
        return f"{int(number):,}".replace(",", " ")
    return f"{number:,.2f}".replace(",", " ")


def _format_period(value: object) -> str:
    return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y")


def _format_deal_count(result: AskResponse) -> tuple[str, list[str], str | None]:
    row = result.rows[0]
    language = result.language
    year_match = re.search(r"\b(20\d{2})\b", result.question)
    deals = _format_number(row["deals"])
    year = year_match.group(1) if year_match else None
    period = ""
    if row.get("min_date") and row.get("max_date"):
        period = f"{_format_period(row['min_date'])}–{_format_period(row['max_date'])}"

    details = []
    if language == "ru":
        title = f"В {year} году заключено <b>{deals}</b> сделок." if year else f"Заключено <b>{deals}</b> сделок."
        if period:
            details.append(f"Период:\n{period}")
        if "deals_not_cancelled" in row and "deals_cancelled" in row:
            details.append(f"Без аннулированных:\n{_format_number(row['deals_not_cancelled'])}")
            details.append(f"Аннулированных:\n{_format_number(row['deals_cancelled'])}")
        insight = None
    else:
        title = f"{year} yilda <b>{deals} ta</b> bitim tuzilgan." if year else f"<b>{deals} ta</b> bitim tuzilgan."
        if period:
            details.append(f"Davr:\n{period}")
        if "deals_not_cancelled" in row and "deals_cancelled" in row:
            details.append(f"Bekor qilinmagan:\n{_format_number(row['deals_not_cancelled'])}")
            details.append(f"Bekor qilingan:\n{_format_number(row['deals_cancelled'])}")
        insight = None

    return title, details, insight


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


def _wants_sql(question: str) -> bool:
    return bool(
        re.search(
            r"\b(show\s+sql|how\s+was\s+it\s+calculated|покажи\s+sql|показать\s+sql|"
            r"как\s+.*рассчит|основание|sql\s+ko'?rsat|qanday\s+hisoblangan|asos)\b",
            question,
            re.I,
        )
    )


def menu_keyboard(language: Language = "uz", *, show_basis: bool = False) -> InlineKeyboardMarkup:
    labels = {
        "uz": [
            ("📊 Statistika", "statistics"),
            ("🏢 Eng faol kompaniyalar", "top_companies"),
            ("📈 Trend", "annual_trend"),
            ("💰 Eng katta bitimlar", "largest_deals"),
            ("🌾 Mahsulotlar", "top_products"),
        ],
        "ru": [
            ("📊 Статистика", "statistics"),
            ("🏢 Самые активные компании", "top_companies"),
            ("📈 Годовой тренд", "annual_trend"),
            ("💰 Крупнейшие сделки", "largest_deals"),
            ("🌾 Топ продуктов", "top_products"),
        ],
    }[language]
    rows = [
            [InlineKeyboardButton(text=label, callback_data=callback)]
            for label, callback in labels
        ]
    if show_basis:
        rows.append([InlineKeyboardButton(text="📄 Asos", callback_data="show_basis")])
    rows.append([
            InlineKeyboardButton(
                text=f"{LANGUAGE_LABELS['uz']} ✓" if language == "uz" else LANGUAGE_LABELS["uz"],
                callback_data="language:uz",
            ),
            InlineKeyboardButton(
                text=f"{LANGUAGE_LABELS['ru']} ✓" if language == "ru" else LANGUAGE_LABELS["ru"],
                callback_data="language:ru",
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _menu_question(callback_data: str, language: Language = "uz") -> str:
    try:
        return MENU_QUESTIONS[callback_data][language]
    except KeyError as exc:
        raise ValueError("Unknown Telegram menu action") from exc


@dispatcher.message(CommandStart())
async def start(message: Message) -> None:
    language = _message_language(message)
    if message.from_user:
        _user_languages[message.from_user.id] = language
    text = START_TEXT if language == "uz" else START_TEXT_RU
    await message.answer(text, reply_markup=menu_keyboard(language))


@router.callback_query(F.data.in_({"language:uz", "language:ru"}))
async def choose_language(callback: CallbackQuery) -> None:
    language: Language = "ru" if callback.data == "language:ru" else "uz"
    _user_languages[callback.from_user.id] = language
    try:
        await callback.answer("Язык изменён" if language == "ru" else "Til o'zgartirildi")
    except Exception:
        logger.exception("Could not acknowledge language selection callback_id=%s", callback.id)
        return

    if isinstance(callback.message, Message):
        text = START_TEXT if language == "uz" else START_TEXT_RU
        await callback.message.answer(text, reply_markup=menu_keyboard(language))


@dispatcher.message()
async def answer_question(message: Message) -> None:
    question = (message.text or message.caption or "").strip()
    if not question:
        language = _message_language(message)
        await message.answer(
            "Savolingizni matn ko'rinishida yuboring yoki menyudan tanlang."
            if language == "uz"
            else "Отправьте вопрос текстом или выберите пункт меню.",
            reply_markup=menu_keyboard(language),
        )
        return

    user_id = message.from_user.id if message.from_user else "unknown"
    logger.info("Question from user_id=%s: %s", user_id, question)
    language = detect_language(question)
    if message.from_user:
        _user_languages[message.from_user.id] = language
    await _answer_question(message, question, user_id, language)


@router.callback_query(F.data.in_(MENU_CALLBACKS))
async def handle_menu_callback(callback: CallbackQuery) -> None:
    try:
        await callback.answer()
    except Exception:
        logger.exception("Could not acknowledge callback_id=%s", callback.id)
        return
    if not isinstance(callback.message, Message) or not callback.data:
        return

    user_id = callback.from_user.id
    language = _user_languages.get(user_id, _message_language(callback.message))
    question = _menu_question(callback.data, language)
    logger.info("Menu action=%s from user_id=%s: %s", callback.data, user_id, question)
    await _answer_question(callback.message, question, user_id, language)


@router.callback_query(F.data == "show_basis")
async def show_basis(callback: CallbackQuery) -> None:
    try:
        await callback.answer()
    except Exception:
        logger.exception("Could not acknowledge basis callback_id=%s", callback.id)
        return

    if not isinstance(callback.message, Message):
        return

    user_id = callback.from_user.id
    result = _last_results.get(user_id)
    language = _user_languages.get(user_id, "uz")
    if result is None:
        text = "Avval savol yuboring." if language == "uz" else "Сначала задайте вопрос."
    else:
        text = _format_basis(result)
    await callback.message.answer(text, reply_markup=menu_keyboard(language))


def _message_language(message: Message) -> Language:
    user_id = message.from_user.id if message.from_user else None
    if user_id in _user_languages:
        return _user_languages[user_id]
    language_code = message.from_user.language_code if message.from_user else None
    if language_code and language_code.lower().startswith("ru"):
        return "ru"
    return "uz"


async def _answer_question(
    message: Message,
    question: str,
    user_id: int | str,
    language: Language,
) -> None:
    try:
        progress_text = ANALYZING_TEXT_RU if language == "ru" else ANALYZING_TEXT
        progress = await message.answer(progress_text)
    except Exception:
        logger.exception("Could not send progress message to user_id=%s", user_id)
        return

    started_at = asyncio.get_running_loop().time()
    try:
        result = await asyncio.to_thread(answer, question, language)
        _last_results[int(user_id)] = result
        elapsed = asyncio.get_running_loop().time() - started_at
        logger.info("Answered user_id=%s in %.3f seconds", user_id, elapsed)
        await progress.edit_text(
            format_telegram_answer(result),
            reply_markup=menu_keyboard(language, show_basis=True),
        )
    except Exception:
        elapsed = asyncio.get_running_loop().time() - started_at
        logger.exception("Failed to answer user_id=%s after %.3f seconds", user_id, elapsed)
        try:
            error_text = ERROR_TEXT_RU if language == "ru" else ERROR_TEXT_UZ
            await progress.edit_text(error_text, reply_markup=menu_keyboard(language))
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