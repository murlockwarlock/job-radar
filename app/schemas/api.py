import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class SearchProfileBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    enabled: bool = True
    source: str = "hh"
    source_host: str = "hh.ru"
    search_text: str = Field(min_length=1, max_length=500)
    area_ids: list[str] = Field(default_factory=list)
    polling_interval_seconds: int = Field(default=900, ge=30)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    excluded_companies: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)
    schedules: list[str] = Field(default_factory=list)
    experience_levels: list[str] = Field(default_factory=list)
    salary_min: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=12)
    only_with_salary: bool = False
    notification_enabled: bool = True
    include_min_matches: int = Field(default=1, ge=1)

    @field_validator("source_host")
    @classmethod
    def validate_source_host(cls, value: str) -> str:
        if value not in {"hh.ru", "hh.kz"}:
            raise ValueError("source_host must be hh.ru or hh.kz")
        return value


class SearchProfileCreate(SearchProfileBase):
    pass


class SearchProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    enabled: bool | None = None
    source: str | None = None
    source_host: str | None = None
    search_text: str | None = Field(default=None, min_length=1, max_length=500)
    area_ids: list[str] | None = None
    polling_interval_seconds: int | None = Field(default=None, ge=30)
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    required_keywords: list[str] | None = None
    excluded_companies: list[str] | None = None
    employment_types: list[str] | None = None
    schedules: list[str] | None = None
    experience_levels: list[str] | None = None
    salary_min: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=12)
    only_with_salary: bool | None = None
    notification_enabled: bool | None = None
    include_min_matches: int | None = Field(default=None, ge=1)

    @field_validator("source_host")
    @classmethod
    def validate_source_host(cls, value: str | None) -> str | None:
        if value is not None and value not in {"hh.ru", "hh.kz"}:
            raise ValueError("source_host must be hh.ru or hh.kz")
        return value


class SearchProfileRead(SearchProfileBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    baseline_started_at: datetime | None
    baseline_completed_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VacancyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source: str
    external_id: str
    source_url: HttpUrl
    alternate_url: HttpUrl | None
    title: str
    employer_name: str | None
    area: str | None
    city: str | None
    salary_from: Decimal | None
    salary_to: Decimal | None
    salary_currency: str | None
    salary_gross: bool | None
    experience: str | None
    employment: str | None
    schedule: str | None
    description: str | None
    key_skills: list[str]
    published_at: datetime | None
    source_updated_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    is_active: bool
    content_hash: str


class MatchResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vacancy_id: uuid.UUID
    search_profile_id: uuid.UUID
    matched: bool
    match_reasons: list[str]
    reject_reasons: list[str]
    processed_at: datetime
    notified_at: datetime | None
    notification_status: str
    notification_error: str | None
    is_baseline: bool


class SearchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    search_profile_id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    status: str
    fetched_count: int
    new_count: int
    matched_count: int
    rejected_count: int
    notified_count: int
    error: str | None


class StatsRead(BaseModel):
    vacancies: int
    active_vacancies: int
    profiles: int
    enabled_profiles: int
    matched_results: int
    notifications_sent: int
    failed_runs: int


class PaginatedVacancies(BaseModel):
    items: list[VacancyRead]
    page: int
    page_size: int
    total: int


class PaginatedProfiles(BaseModel):
    items: list[SearchProfileRead]
    page: int
    page_size: int
    total: int


class PaginatedRuns(BaseModel):
    items: list[SearchRunRead]
    page: int
    page_size: int
    total: int


class ManualRunResponse(BaseModel):
    run_id: uuid.UUID
    status: str
