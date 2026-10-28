import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionFactory
from app.filtering.engine import FilterEngine
from app.models.entities import (
    MatchResult,
    NotificationDelivery,
    SearchProfile,
    SearchRun,
    Vacancy,
    utcnow,
)
from app.providers.base import BaseJobProvider, JobDTO
from app.providers.factory import build_provider

logger = logging.getLogger(__name__)


def content_hash(dto: JobDTO) -> str:
    payload = {
        key: getattr(dto, key)
        for key in (
            "title",
            "employer_name",
            "area",
            "city",
            "salary_from",
            "salary_to",
            "salary_currency",
            "salary_gross",
            "experience",
            "employment",
            "schedule",
            "description",
            "key_skills",
            "source_url",
        )
    }
    encoded = json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def should_enqueue_notification(
    matched: bool,
    notification_enabled: bool,
    is_baseline: bool,
    send_on_initial_sync: bool,
) -> bool:
    return matched and notification_enabled and (not is_baseline or send_on_initial_sync)


def vacancy_values(dto: JobDTO, digest: str, existing: Vacancy | None = None) -> dict[str, Any]:
    now = utcnow()
    values = {
        "source": dto.source,
        "external_id": dto.external_id,
        "source_url": dto.source_url,
        "alternate_url": dto.alternate_url,
        "title": dto.title,
        "employer_name": dto.employer_name,
        "employer_external_id": dto.employer_external_id,
        "area": dto.area,
        "area_id": dto.area_id,
        "city": dto.city,
        "salary_from": dto.salary_from,
        "salary_to": dto.salary_to,
        "salary_currency": dto.salary_currency,
        "salary_gross": dto.salary_gross,
        "experience": dto.experience,
        "experience_id": dto.experience_id,
        "employment": dto.employment,
        "employment_id": dto.employment_id,
        "schedule": dto.schedule,
        "schedule_id": dto.schedule_id,
        "description": dto.description,
        "key_skills": dto.key_skills,
        "published_at": dto.published_at,
        "source_updated_at": dto.source_updated_at,
        "last_seen_at": now,
        "is_active": True,
        "raw_payload": dto.raw_payload,
        "content_hash": digest,
    }
    if existing is None:
        values["first_seen_at"] = now
    return values


async def upsert_vacancy(session: AsyncSession, dto: JobDTO) -> tuple[Vacancy, bool, bool]:
    existing = await session.scalar(
        select(Vacancy).where(Vacancy.source == dto.source, Vacancy.external_id == dto.external_id)
    )
    digest = content_hash(dto)
    values = vacancy_values(dto, digest, existing)
    if existing is None:
        dialect = session.bind.dialect.name if session.bind else "postgresql"
        insert_stmt = sqlite_insert(Vacancy) if dialect == "sqlite" else pg_insert(Vacancy)
        stmt = insert_stmt.values(**values).on_conflict_do_nothing(
            index_elements=["source", "external_id"]
        )
        await session.execute(stmt)
        await session.flush()
        existing = await session.scalar(
            select(Vacancy).where(
                Vacancy.source == dto.source, Vacancy.external_id == dto.external_id
            )
        )
        if existing is None:
            raise RuntimeError("Vacancy upsert did not return a row")
        is_new = existing.first_seen_at == existing.last_seen_at
        changed = existing.content_hash != digest
        if changed:
            for key, value in values.items():
                if key not in {"source", "external_id", "first_seen_at"}:
                    setattr(existing, key, value)
        return existing, is_new, changed
    changed = existing.content_hash != digest
    for key, value in values.items():
        if key not in {"source", "external_id", "first_seen_at"}:
            setattr(existing, key, value)
    await session.flush()
    return existing, False, changed


@asynccontextmanager
async def profile_lock(profile_id: uuid.UUID) -> AsyncIterator[bool]:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    lock = redis.lock(
        f"job-radar:profile:{profile_id}", timeout=settings.redis_lock_ttl_seconds, blocking=False
    )
    acquired = await lock.acquire(blocking=False)
    heartbeat: asyncio.Task[None] | None = None
    if acquired:

        async def renew() -> None:
            while True:
                await asyncio.sleep(max(30, settings.redis_lock_ttl_seconds // 3))
                try:
                    await lock.extend(settings.redis_lock_ttl_seconds)
                except Exception:
                    logger.warning(
                        "failed to renew profile lock",
                        extra={"search_profile_id": str(profile_id)},
                    )
                    return

        heartbeat = asyncio.create_task(renew())
    try:
        yield acquired
    finally:
        if heartbeat:
            heartbeat.cancel()
        if acquired:
            try:
                await lock.release()
            except Exception:
                logger.warning(
                    "failed to release profile lock", extra={"search_profile_id": str(profile_id)}
                )
        await redis.aclose()


async def run_profile(profile_id: uuid.UUID, run_id: uuid.UUID | None = None) -> uuid.UUID:
    settings = get_settings()
    async with profile_lock(profile_id) as acquired:
        if not acquired:
            logger.info(
                "profile run skipped because lock is held",
                extra={"search_profile_id": str(profile_id)},
            )
            return run_id or uuid.uuid4()
        async with AsyncSessionFactory() as session:
            profile = await session.get(SearchProfile, profile_id)
            if profile is None:
                raise LookupError("Search profile not found")
            if run_id:
                run = await session.get(SearchRun, run_id)
                if run is None:
                    run = SearchRun(id=run_id, search_profile_id=profile_id, status="running")
                    session.add(run)
            else:
                run = SearchRun(search_profile_id=profile_id, status="running")
                session.add(run)
            if profile.baseline_started_at is None:
                profile.baseline_started_at = utcnow()
            run.status = "running"
            run.heartbeat_at = utcnow()
            await session.commit()
            run_id = run.id

        filter_engine = FilterEngine()
        provider: BaseJobProvider | None = None
        fetched = new = matched = rejected = notified = 0
        error_messages: list[str] = []
        successful = True
        try:
            provider = build_provider(profile.source)
            async with AsyncSessionFactory() as session:
                profile = await session.get(SearchProfile, profile_id)
                if profile is None:
                    raise LookupError("Search profile not found")
                async for dto in provider.search(profile):
                    fetched += 1
                    try:
                        vacancy, is_new, _changed = await upsert_vacancy(session, dto)
                        result = filter_engine.evaluate(vacancy, profile)
                        is_baseline = profile.baseline_completed_at is None
                        match = await session.scalar(
                            select(MatchResult).where(
                                MatchResult.vacancy_id == vacancy.id,
                                MatchResult.search_profile_id == profile.id,
                            )
                        )
                        if match is None:
                            match = MatchResult(
                                vacancy_id=vacancy.id,
                                search_profile_id=profile.id,
                                search_run_id=run_id,
                            )
                            session.add(match)
                        match.search_run_id = run_id
                        match.matched = result.matched
                        match.match_reasons = result.match_reasons
                        match.reject_reasons = result.reject_reasons
                        match.processed_at = utcnow()
                        match.content_hash = vacancy.content_hash
                        match.is_baseline = is_baseline
                        if result.matched:
                            matched += 1
                        else:
                            rejected += 1
                        if is_new:
                            new += 1
                        if should_enqueue_notification(
                            result.matched,
                            profile.notification_enabled,
                            is_baseline,
                            settings.send_notifications_on_initial_sync,
                        ):
                            recipient = (
                                str(settings.telegram_admin_chat_id)
                                if settings.telegram_admin_chat_id
                                else None
                            )
                            if recipient:
                                delivery_stmt = (
                                    pg_insert(NotificationDelivery).values(
                                        vacancy_id=vacancy.id,
                                        profile_id=profile.id,
                                        recipient_key=recipient,
                                        status="pending",
                                    )
                                    if session.bind and session.bind.dialect.name != "sqlite"
                                    else sqlite_insert(NotificationDelivery).values(
                                        vacancy_id=vacancy.id,
                                        profile_id=profile.id,
                                        recipient_key=recipient,
                                        status="pending",
                                    )
                                )
                                delivery_stmt = delivery_stmt.on_conflict_do_nothing(
                                    index_elements=["vacancy_id", "recipient_key"]
                                )
                                delivery_result = await session.execute(delivery_stmt)
                                if getattr(delivery_result, "rowcount", 0):
                                    match.notification_status = "pending"
                                    notified += 1
                        await session.commit()
                    except Exception as item_error:
                        await session.rollback()
                        error_messages.append(f"vacancy:{dto.external_id}: {item_error}")
                        logger.exception(
                            "vacancy processing failed",
                            extra={"search_profile_id": str(profile_id), "run_id": str(run_id)},
                        )
                run = await session.get(SearchRun, run_id)
                profile = await session.get(SearchProfile, profile_id)
                if run and profile:
                    run.fetched_count = fetched
                    run.new_count = new
                    run.matched_count = matched
                    run.rejected_count = rejected
                    run.notified_count = notified
                    run.finished_at = utcnow()
                    run.heartbeat_at = utcnow()
                    run.status = "partial" if error_messages else "success"
                    run.error = "\n".join(error_messages)[:10000] if error_messages else None
                    if run.status == "success":
                        profile.baseline_completed_at = profile.baseline_started_at or utcnow()
                    await session.commit()
        except Exception as exc:
            successful = False
            error_messages.append(str(exc))
            logger.exception(
                "profile run failed",
                extra={"search_profile_id": str(profile_id), "run_id": str(run_id)},
            )
            async with AsyncSessionFactory() as session:
                run = await session.get(SearchRun, run_id)
                if run:
                    run.status = "failed"
                    run.finished_at = utcnow()
                    run.error = "\n".join(error_messages)[:10000]
                    await session.commit()
        finally:
            if provider is not None:
                await provider.close()
        logger.info(
            "profile run completed",
            extra={
                "source": "hh",
                "search_profile_id": str(profile_id),
                "run_id": str(run_id),
                "count_fetched": fetched,
                "count_new": new,
                "count_matched": matched,
                "count_rejected": rejected,
                "notifications_sent": notified,
                "success": successful,
            },
        )
        return run_id


async def dispatch_due_profiles(enqueue: Any) -> int:
    now = utcnow()
    dispatched = 0
    queued: list[tuple[str, str]] = []
    async with AsyncSessionFactory() as session:
        profiles = await session.scalars(
            select(SearchProfile)
            .where(SearchProfile.enabled, SearchProfile.next_run_at <= now)
            .with_for_update(skip_locked=True)
        )
        for profile in profiles:
            try:
                active_run = await session.scalar(
                    select(SearchRun.id).where(
                        SearchRun.search_profile_id == profile.id,
                        SearchRun.status.in_(["queued", "running"]),
                    )
                )
                if active_run:
                    profile.next_run_at = now + timedelta(seconds=profile.polling_interval_seconds)
                    continue
                run = SearchRun(search_profile_id=profile.id, status="queued")
                profile.next_run_at = now + timedelta(seconds=profile.polling_interval_seconds)
                session.add(run)
                await session.flush()
                queued.append((str(profile.id), str(run.id)))
                dispatched += 1
            except Exception:
                logger.exception(
                    "failed to enqueue profile", extra={"search_profile_id": str(profile.id)}
                )
        await session.commit()
    for profile_id, run_id in queued:
        try:
            enqueue(profile_id, run_id)
        except Exception:
            logger.exception(
                "failed to publish profile task",
                extra={"search_profile_id": profile_id, "run_id": run_id},
            )
    return dispatched


async def send_pending_notifications(notifier: Any) -> int:
    sent = 0
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        for _ in range(50):
            delivery = await session.scalar(
                select(NotificationDelivery)
                .where(
                    NotificationDelivery.status.in_(["pending", "failed"]),
                    NotificationDelivery.next_attempt_at <= utcnow(),
                )
                .order_by(NotificationDelivery.next_attempt_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if delivery is None:
                break
            delivery.status = "sending"
            delivery.attempts += 1
            await session.commit()
            vacancy = await session.get(Vacancy, delivery.vacancy_id)
            profile = (
                await session.get(SearchProfile, delivery.profile_id)
                if delivery.profile_id
                else None
            )
            match = (
                await session.scalar(
                    select(MatchResult).where(
                        MatchResult.vacancy_id == delivery.vacancy_id,
                        MatchResult.search_profile_id == delivery.profile_id,
                    )
                )
                if delivery.profile_id
                else None
            )
            if vacancy is None:
                delivery.status = "failed"
                delivery.last_error = "vacancy missing"
                await session.commit()
                continue
            try:
                message_id = await notifier.send(
                    vacancy,
                    delivery,
                    profile,
                    match.match_reasons if match else None,
                )
                delivery.status = "sent"
                delivery.sent_at = utcnow()
                delivery.telegram_message_id = message_id
                delivery.last_error = None
                if match:
                    match.notified_at = utcnow()
                    match.notification_status = "sent"
                    match.notification_error = None
                sent += 1
            except Exception as exc:
                delivery.status = "failed"
                delivery.last_error = str(exc)[:2000]
                delivery.unknown_delivery = True
                delivery.next_attempt_at = utcnow() + timedelta(
                    seconds=min(3600, 2 ** min(delivery.attempts, 10))
                )
                if match:
                    match.notification_status = "failed"
                    match.notification_error = str(exc)[:2000]
                logger.exception(
                    "notification delivery failed", extra={"delivery_id": str(delivery.id)}
                )
            await session.commit()
    logger.info(
        "notification batch completed",
        extra={"notifications_sent": sent, "recipient": settings.telegram_admin_chat_id},
    )
    return sent
