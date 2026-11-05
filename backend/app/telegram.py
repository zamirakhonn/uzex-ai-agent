from __future__ import annotations

import asyncio
import logging
import re
import secrets
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, Update
from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from .config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL
from .pipeline import answer
from .schemas import AskResponse

logger = logging.getLogger("uzex.telegram")
router = APIRouter()
dispatcher = Dispatcher()
bot: Bot | None = None
_webhook_secret: str | None = None

START_TEXT = (
    "🤖 Salom!\n"
    "Men UZEX AI Agentman.\n"
    "UZEX birja ma'lumotlari bo'yicha savol bering."
)
ANALYZING_TEXT = "🔎 Ma'lumotlar tahlil qilinmoqda..."
ERROR_TEXT = "❌ Xatolik yuz berdi. Iltimos qayta urinib ko'ring."


def format_telegram_answer(result: AskResponse) -> str:
    if (
        result.language != "uz"
        or result.intent != "count_deals"
        or not result.found
        or not result.verification.passed
        or not result.rows
    ):
        return result.answer

    year_match = re.search(r"\b(202[2-6])\b", result.question)
    if not year_match:
        return result.answer

    row = result.rows[0]
    try:
        deals = int(row["deals"])
        amount_trillion = float(row["amount_uzs"]) / 1_000_000_000_000
        period_start = datetime.fromisoformat(str(row["min_date"])).strftime("%d.%m.%Y")
        period_end = datetime.fromisoformat(str(row["max_date"])).strftime("%d.%m.%Y")
    except (KeyError, TypeError, ValueError):
        return result.answer

    if result.confidence >= 0.85:
        confidence = "🟢 High"
    elif result.confidence >= 0.6:
        confidence = "🟡 Medium"
    else:
        confidence = "🔴 Low"

    return (
        "📊 UZEX AI ANALYSIS\n\n"
        f"{year_match.group(1)} yilda birjada:\n\n"
        f"📦 {deals:,} ta bitim\n"
        f"💰 {amount_trillion:.2f} trln so'm savdo hajmi\n\n"
        "📅 Davr:\n"
        f"{period_start} — {period_end}\n\n"
        "✅ VERIFIED DATA\n\n"
        "Source:\n"
        "UZEX exchange database\n\n"
        "Evidence:\n"
        f"{deals:,} verified transaction records analyzed\n\n"
        "Confidence:\n"
        f"{confidence}\n\n"
        "💡 Try:\n"
        "🏢 Eng faol kompaniyalar\n"
        "📈 Yillik trend\n"
        "💰 Eng katta bitimlar"
    )


@dispatcher.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(START_TEXT)


@dispatcher.message(F.text)
async def answer_question(message: Message) -> None:
    question = (message.text or "").strip()
    if not question:
        return

    user_id = message.from_user.id if message.from_user else "unknown"
    logger.info("Question from user_id=%s: %s", user_id, question)

    try:
        progress = await message.answer(ANALYZING_TEXT)
    except Exception:
        logger.exception("Could not send progress message to user_id=%s", user_id)
        return

    started_at = asyncio.get_running_loop().time()
    try:
        result = await asyncio.to_thread(answer, question)
        logger.info(
            "Answered user_id=%s in %.3f seconds",
            user_id,
            asyncio.get_running_loop().time() - started_at,
        )
        await progress.edit_text(format_telegram_answer(result))
    except Exception:
        logger.exception(
            "Failed to answer user_id=%s after %.3f seconds",
            user_id,
            asyncio.get_running_loop().time() - started_at,
        )
        try:
            await progress.edit_text(ERROR_TEXT)
        except Exception:
            logger.exception("Could not send error response to user_id=%s", user_id)


def _webhook_endpoint(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise RuntimeError("WEBHOOK_URL must be an HTTPS URL without query or fragment")
    if parsed.path not in {"", "/", "/telegram/webhook"}:
        raise RuntimeError("WEBHOOK_URL must be the service URL or end in /telegram/webhook")
    return urlunsplit((parsed.scheme, parsed.netloc, "/telegram/webhook", "", ""))


async def initialize_telegram() -> None:
    global bot, _webhook_secret

    if not TELEGRAM_BOT_TOKEN or not WEBHOOK_URL:
        logger.warning("Telegram webhook disabled; set TELEGRAM_BOT_TOKEN and WEBHOOK_URL")
        return

    webhook_url = _webhook_endpoint(WEBHOOK_URL)
    _webhook_secret = secrets.token_urlsafe(32)
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=_webhook_secret,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    except Exception:
        await bot.session.close()
        bot = None
        _webhook_secret = None
        raise
    logger.info("Telegram webhook registered at %s", webhook_url)


async def close_telegram() -> None:
    global bot, _webhook_secret
    if bot is not None:
        await bot.session.close()
    bot = None
    _webhook_secret = None


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> dict[str, bool]:
    if bot is None or _webhook_secret is None:
        raise HTTPException(status_code=503, detail="Telegram webhook is not configured")

    provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secrets.compare_digest(provided_secret, _webhook_secret):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    try:
        payload = await request.json()
        update = Update.model_validate(payload, context={"bot": bot})
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Telegram update") from exc

    await dispatcher.feed_update(bot, update)
    return {"ok": True}