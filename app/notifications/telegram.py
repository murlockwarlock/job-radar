import html
import logging
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _esc(value: Any) -> str:
    return html.escape(str(value or "—"), quote=False)


def format_vacancy_message(
    vacancy: Any, reasons: list[str] | None = None, profile_name: str | None = None
) -> str:
    salary = "—"
    if vacancy.salary_from is not None or vacancy.salary_to is not None:
        low = vacancy.salary_from if vacancy.salary_from is not None else ""
        high = vacancy.salary_to if vacancy.salary_to is not None else ""
        salary = f"{low}–{high} {vacancy.salary_currency or ''}".strip()
    lines = [
        "🔥 <b>Новая вакансия</b>",
        "",
        f"<b>{_esc(vacancy.title)}</b>",
        f"Компания: {_esc(vacancy.employer_name)}",
        f"Локация: {_esc(vacancy.city or vacancy.area)}",
        f"График: {_esc(vacancy.schedule)}",
        f"Зарплата: {_esc(salary)}",
        f"Опыт: {_esc(vacancy.experience)}",
    ]
    if reasons:
        lines.extend(["", "<b>Совпало:</b>"])
        lines.extend(f"• {_esc(reason)}" for reason in reasons[:12])
    lines.extend(
        [
            "",
            f"Ссылка: {_esc(vacancy.source_url)}",
            f"Источник: {_esc(vacancy.source.upper())}",
        ]
    )
    if profile_name:
        lines.append(f"Профиль: {_esc(profile_name)}")
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: int | None = None) -> None:
        settings = get_settings()
        self.token = token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_admin_chat_id
        if not self.token or self.chat_id is None:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID are required")

    async def send(
        self,
        vacancy: Any,
        delivery: Any,
        profile: Any | None = None,
        reasons: list[str] | None = None,
    ) -> int:
        assert self.token is not None
        assert self.chat_id is not None
        token = self.token
        target_chat_id = self.chat_id
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть вакансию", url=vacancy.source_url)],
            ]
        )
        text = format_vacancy_message(vacancy, reasons, getattr(profile, "name", None))
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(
                    (TelegramRetryAfter, TelegramNetworkError, TelegramServerError)
                ),
                wait=wait_random_exponential(multiplier=1, max=60),
                stop=stop_after_attempt(5),
                reraise=True,
            ):
                with attempt:
                    message = await bot.send_message(
                        chat_id=target_chat_id,
                        text=text,
                        reply_markup=keyboard,
                        disable_web_page_preview=True,
                    )
                    return message.message_id
        except (TelegramBadRequest, TelegramForbiddenError):
            raise
        finally:
            await bot.session.close()
        raise RuntimeError("Telegram send did not return a message")
