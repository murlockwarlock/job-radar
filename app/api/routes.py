import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import SearchProfile, SearchRun, Vacancy
from app.schemas.api import (
    ManualRunResponse,
    PaginatedProfiles,
    PaginatedRuns,
    PaginatedVacancies,
    SearchProfileCreate,
    SearchProfileRead,
    SearchProfileUpdate,
    SearchRunRead,
    StatsRead,
    VacancyRead,
)
from app.services.profiles import (
    create_queued_run,
    list_profiles,
    list_runs,
    list_vacancies,
    stats,
)
from app.tasks.jobs import process_profile_task

router = APIRouter(prefix="/api/v1")
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/vacancies", response_model=PaginatedVacancies)
async def get_vacancies(
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    source: str | None = None,
    active: bool | None = None,
) -> PaginatedVacancies:
    items, total = await list_vacancies(session, page, page_size, source, active)
    return PaginatedVacancies(items=items, page=page, page_size=page_size, total=total)


@router.get("/vacancies/{vacancy_id}", response_model=VacancyRead)
async def get_vacancy(vacancy_id: uuid.UUID, session: SessionDep) -> Vacancy:
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return vacancy


@router.get("/search-profiles", response_model=PaginatedProfiles)
async def get_profiles(
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> PaginatedProfiles:
    items, total = await list_profiles(session, page, page_size)
    return PaginatedProfiles(items=items, page=page, page_size=page_size, total=total)


@router.post(
    "/search-profiles", response_model=SearchProfileRead, status_code=status.HTTP_201_CREATED
)
async def create_profile(payload: SearchProfileCreate, session: SessionDep) -> SearchProfile:
    existing = await session.scalar(select(SearchProfile).where(SearchProfile.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Profile name already exists")
    profile = SearchProfile(**payload.model_dump(), next_run_at=datetime.now(UTC))
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("/search-profiles/{profile_id}", response_model=SearchProfileRead)
async def get_profile(profile_id: uuid.UUID, session: SessionDep) -> SearchProfile:
    profile = await session.get(SearchProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Search profile not found")
    return profile


@router.patch("/search-profiles/{profile_id}", response_model=SearchProfileRead)
async def update_profile(
    profile_id: uuid.UUID, payload: SearchProfileUpdate, session: SessionDep
) -> SearchProfile:
    profile = await session.get(SearchProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Search profile not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(profile, key, value)
    if profile.enabled and (profile.next_run_at is None or "polling_interval_seconds" in updates):
        profile.next_run_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.delete("/search-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: uuid.UUID, session: SessionDep) -> None:
    profile = await session.get(SearchProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Search profile not found")
    profile.enabled = False
    await session.commit()


@router.post(
    "/search-profiles/{profile_id}/run",
    response_model=ManualRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_profile_now(profile_id: uuid.UUID, session: SessionDep) -> ManualRunResponse:
    try:
        run = await create_queued_run(session, profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    process_profile_task.delay(str(profile_id), str(run.id))
    return ManualRunResponse(run_id=run.id, status=run.status)


@router.get("/runs", response_model=PaginatedRuns)
async def get_runs(
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> PaginatedRuns:
    items, total = await list_runs(session, page, page_size)
    return PaginatedRuns(items=items, page=page, page_size=page_size, total=total)


@router.get("/runs/{run_id}", response_model=SearchRunRead)
async def get_run(run_id: uuid.UUID, session: SessionDep) -> SearchRun:
    run = await session.get(SearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/stats", response_model=StatsRead)
async def get_stats(session: SessionDep) -> StatsRead:
    return StatsRead(**(await stats(session)))
