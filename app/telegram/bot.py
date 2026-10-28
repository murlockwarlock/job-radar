import logging

from aiogram import Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionFactory
from app.models.entities import Vacancy
from app.services.profiles import stats
from app.telegram.callbacks import CallbackAction

logger = logging.getLogger(__name__)
router = Router()


async def _is_admin(message: Message) -> bool:
    admin_id = get_settings().telegram_admin_chat_id
    return admin_id is not None and message.chat.id == admin_id


@router.message(Command("status"))
async def status_command(message: Message) -> None:
    if not await _is_admin(message):
        return
    async with AsyncSessionFactory() as session:
        values = await stats(session)
    await message.answer(
        "<b>Job Radar</b>\n"
        f"Вакансий: {values['vacancies']}\n"
        f"Профилей: {values['enabled_profiles']}/{values['profiles']}\n"
        f"Активных вакансий: {values['active_vacancies']}"
    )


@router.message(Command("stats"))
async def stats_command(message: Message) -> None:
    if not await _is_admin(message):
        return
    async with AsyncSessionFactory() as session:
        values = await stats(session)
    await message.answer("\n".join(f"{key}: {value}" for key, value in values.items()))


@router.message(Command("last"))
async def last_command(message: Message) -> None:
    if not await _is_admin(message):
        return
    async with AsyncSessionFactory() as session:
        vacancy = await session.scalar(
            select(Vacancy).order_by(Vacancy.first_seen_at.desc()).limit(1)
        )
    if vacancy is None:
        await message.answer("Новых вакансий пока нет.")
        return
    await message.answer(f"Последняя вакансия: <b>{vacancy.title}</b>\n{vacancy.source_url}")


@router.message(Command("profiles"))
async def profiles_command(message: Message) -> None:
    if not await _is_admin(message):
        return
    from app.models.entities import SearchProfile

    async with AsyncSessionFactory() as session:
        profiles = list(await session.scalars(select(SearchProfile).order_by(SearchProfile.name)))
    if not profiles:
        await message.answer("Профилей нет.")
        return
    await message.answer(
        "\n".join(f"{'✅' if profile.enabled else '⏸'} {profile.name}" for profile in profiles)
    )


@router.callback_query()
async def callback_router(callback: object) -> None:
    callback_data = getattr(callback, "data", None)
    action = CallbackAction.parse(callback_data if isinstance(callback_data, str) else None)
    callback_message = getattr(callback, "message", None)
    chat = getattr(callback_message, "chat", None)
    admin_id = get_settings().telegram_admin_chat_id
    if admin_id is None or getattr(chat, "id", None) != admin_id:
        return
    if action and action.action == "blacklist_employer":
        answer = getattr(callback, "answer", None)
        if answer:
            await answer(
                "Управление blacklist работодателей будет доступно позже.", show_alert=True
            )


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher
