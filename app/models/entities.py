import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def utcnow() -> datetime:
    return datetime.now(UTC)


JsonType = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class SearchProfile(TimestampMixin, Base):
    __tablename__ = "search_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="hh", nullable=False)
    source_host: Mapped[str] = mapped_column(String(40), default="hh.ru", nullable=False)
    search_text: Mapped[str] = mapped_column(String(500), nullable=False)
    area_ids: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    polling_interval_seconds: Mapped[int] = mapped_column(Integer, default=900, nullable=False)
    include_keywords: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    exclude_keywords: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    required_keywords: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    excluded_companies: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    employment_types: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    schedules: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    experience_levels: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    only_with_salary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_min_matches: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    baseline_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    baseline_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    runs: Mapped[list["SearchRun"]] = relationship(back_populates="profile")
    match_results: Mapped[list["MatchResult"]] = relationship(back_populates="profile")


class Vacancy(TimestampMixin, Base):
    __tablename__ = "vacancies"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_vacancy_source_external"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    alternate_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    employer_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    employer_external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    area: Mapped[str | None] = mapped_column(String(300), nullable=True)
    area_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    city: Mapped[str | None] = mapped_column(String(300), nullable=True)
    salary_from: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_to: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    salary_gross: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    experience: Mapped[str | None] = mapped_column(String(120), nullable=True)
    experience_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    employment: Mapped[str | None] = mapped_column(String(120), nullable=True)
    employment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    schedule: Mapped[str | None] = mapped_column(String(120), nullable=True)
    schedule_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_skills: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    match_results: Mapped[list["MatchResult"]] = relationship(back_populates="vacancy")
    deliveries: Mapped[list["NotificationDelivery"]] = relationship(back_populates="vacancy")


class SearchRun(Base):
    __tablename__ = "search_runs"
    __table_args__ = (Index("ix_search_runs_profile_started", "search_profile_id", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    search_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="CASCADE")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running", nullable=False)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notified_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped[SearchProfile] = relationship(back_populates="runs")


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "search_profile_id", name="uq_match_vacancy_profile"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    search_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="CASCADE")
    )
    search_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("search_runs.id", ondelete="SET NULL")
    )
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
    match_reasons: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    reject_reasons: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notification_status: Mapped[str] = mapped_column(
        String(30), default="not_requested", nullable=False
    )
    notification_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    vacancy: Mapped[Vacancy] = relationship(back_populates="match_results")
    profile: Mapped[SearchProfile] = relationship(back_populates="match_results")


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "recipient_key", name="uq_delivery_vacancy_recipient"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="SET NULL")
    )
    recipient_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    unknown_delivery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    vacancy: Mapped[Vacancy] = relationship(back_populates="deliveries")
