from __future__ import annotations

import asyncio
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from backend.app.catalog import catalog
from backend.app.ingest import build_database
from backend.app.pipeline import answer
from backend.app.schemas import AskResponse

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("uzex.telegram_bot")
dispatcher = Dispatcher()

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

	started_at = perf_counter()
	try:
		result = await asyncio.to_thread(answer, question)
		elapsed = perf_counter() - started_at
		logger.info("Answered user_id=%s in %.3f seconds", user_id, elapsed)
		await progress.edit_text(format_telegram_answer(result))
	except Exception:
		elapsed = perf_counter() - started_at
		logger.exception("Failed to answer user_id=%s after %.3f seconds", user_id, elapsed)
		try:
			await progress.edit_text(ERROR_TEXT)
		except Exception:
			logger.exception("Could not send error response to user_id=%s", user_id)


async def main() -> None:
	import os

	token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
	if not token:
		raise RuntimeError(
			"TELEGRAM_BOT_TOKEN is missing. Add it to the project root .env file."
		)

	logger.info("Initializing DuckDB and entity catalog")
	await asyncio.to_thread(build_database, force=False)
	await asyncio.to_thread(catalog.load)

	async with Bot(token=token) as bot:
		await bot.get_me()
		print("🤖 UZEX AI Telegram bot started", flush=True)
		await dispatcher.start_polling(bot)


if __name__ == "__main__":
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		logger.info("Telegram bot stopped")
