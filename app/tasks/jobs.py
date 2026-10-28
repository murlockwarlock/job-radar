import asyncio
import logging
import uuid
from typing import Any

from app.notifications.telegram import TelegramNotifier
from app.services.monitoring import dispatch_due_profiles, run_profile, send_pending_notifications
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=5)  # type: ignore[misc]
def process_profile_task(self: Any, profile_id: str, run_id: str | None = None) -> str:
    resolved_run_id = asyncio.run(
        run_profile(uuid.UUID(profile_id), uuid.UUID(run_id) if run_id else None)
    )
    return str(resolved_run_id)


@celery_app.task  # type: ignore[misc]
def dispatch_due_profiles_task() -> int:
    from app.tasks.jobs import process_profile_task

    return asyncio.run(
        dispatch_due_profiles(
            lambda profile_id, run_id: process_profile_task.delay(profile_id, run_id)
        )
    )


@celery_app.task  # type: ignore[misc]
def send_pending_notifications_task() -> int:
    try:
        notifier = TelegramNotifier()
    except RuntimeError:
        logger.info("Telegram notifications disabled because credentials are missing")
        return 0
    return asyncio.run(send_pending_notifications(notifier))
