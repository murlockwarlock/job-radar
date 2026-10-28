import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import MatchResult, NotificationDelivery, SearchProfile, SearchRun, Vacancy


def utcnow() -> datetime:
    return datetime.now(UTC)


def profile_to_dict(profile: SearchProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "enabled": profile.enabled,
        "source": profile.source,
        "source_host": profile.source_host,
        "search_text": profile.search_text,
        "area_ids": profile.area_ids,
        "polling_interval_seconds": profile.polling_interval_seconds,
        "include_keywords": profile.include_keywords,
        "exclude_keywords": profile.exclude_keywords,
        "required_keywords": profile.required_keywords,
        "excluded_companies": profile.excluded_companies,
        "employment_types": profile.employment_types,
        "schedules": profile.schedules,
        "experience_levels": profile.experience_levels,
        "salary_min": profile.salary_min,
        "currency": profile.currency,
        "only_with_salary": profile.only_with_salary,
        "notification_enabled": profile.notification_enabled,
        "include_min_matches": profile.include_min_matches,
    }


async def seed_profiles(session: AsyncSession) -> SearchProfile | None:
    if await session.scalar(select(func.count(SearchProfile.id))):
        return None
    profile = SearchProfile(
        name="Mining Kazakhstan",
        source="hh",
        source_host="hh.kz",
        search_text="горный инженер планирование горных работ бурение карьер рудник",
        area_ids=["40"],
        polling_interval_seconds=900,
        include_keywords=[
            "горный инженер",
            "инженер по планированию",
            "инженер по горным работам",
            "младший горный инженер",
            "буровой мастер",
            "мастер по бурению",
            "планирование горных работ",
            "производственная отчетность",
            "техническая отчетность",
            "micromine",
            "surpac",
            "datamine",
            "карьер",
            "рудник",
            "огр",
            "открытые горные работы",
        ],
        exclude_keywords=[
            "строительство",
            "общестроительные",
            "кс-2",
            "кс-3",
            "овик",
            "слаботочные системы",
            "монолит",
            "гражданское строительство",
        ],
        include_min_matches=1,
        notification_enabled=True,
        next_run_at=datetime.now(UTC),
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def create_queued_run(session: AsyncSession, profile_id: uuid.UUID) -> SearchRun:
    profile = await session.get(SearchProfile, profile_id)
    if profile is None:
        raise LookupError("Search profile not found")
    running = await session.scalar(
        select(SearchRun.id).where(
            SearchRun.search_profile_id == profile_id,
            SearchRun.status.in_(["queued", "running"]),
        )
    )
    if running:
        raise RuntimeError("A run for this profile is already queued or running")
    run = SearchRun(search_profile_id=profile_id, status="queued")
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def list_profiles(
    session: AsyncSession, page: int, page_size: int
) -> tuple[list[SearchProfile], int]:
    total = int(await session.scalar(select(func.count(SearchProfile.id))) or 0)
    rows = await session.scalars(
        select(SearchProfile)
        .order_by(SearchProfile.created_at)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


async def list_vacancies(
    session: AsyncSession,
    page: int,
    page_size: int,
    source: str | None = None,
    active: bool | None = None,
) -> tuple[list[Vacancy], int]:
    query = select(Vacancy)
    count = select(func.count(Vacancy.id))
    if source:
        query = query.where(Vacancy.source == source)
        count = count.where(Vacancy.source == source)
    if active is not None:
        query = query.where(Vacancy.is_active == active)
        count = count.where(Vacancy.is_active == active)
    total = int(await session.scalar(count) or 0)
    rows = await session.scalars(
        query.order_by(Vacancy.published_at.desc().nullslast(), Vacancy.first_seen_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


async def list_runs(
    session: AsyncSession, page: int, page_size: int
) -> tuple[list[SearchRun], int]:
    total = int(await session.scalar(select(func.count(SearchRun.id))) or 0)
    rows = await session.scalars(
        select(SearchRun)
        .order_by(SearchRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


async def stats(session: AsyncSession) -> dict[str, int]:
    return {
        "vacancies": int(await session.scalar(select(func.count(Vacancy.id))) or 0),
        "active_vacancies": int(
            await session.scalar(select(func.count(Vacancy.id)).where(Vacancy.is_active)) or 0
        ),
        "profiles": int(await session.scalar(select(func.count(SearchProfile.id))) or 0),
        "enabled_profiles": int(
            await session.scalar(select(func.count(SearchProfile.id)).where(SearchProfile.enabled))
            or 0
        ),
        "matched_results": int(
            await session.scalar(select(func.count(MatchResult.id)).where(MatchResult.matched)) or 0
        ),
        "notifications_sent": int(
            await session.scalar(
                select(func.count(NotificationDelivery.id)).where(
                    NotificationDelivery.status == "sent"
                )
            )
            or 0
        ),
        "failed_runs": int(
            await session.scalar(
                select(func.count(SearchRun.id)).where(SearchRun.status == "failed")
            )
            or 0
        ),
    }
