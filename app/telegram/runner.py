import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.telegram.bot import build_dispatcher


async def run() -> None:
    settings = get_settings()
    if not settings.telegram_polling_enabled or not settings.telegram_bot_token:
        logging.getLogger(__name__).info("Telegram polling disabled")
        await asyncio.Event().wait()
        return
    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dispatcher = build_dispatcher()
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    configure_logging()
    asyncio.run(run())
