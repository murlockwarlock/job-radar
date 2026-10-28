import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "search_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source", sa.String(40), nullable=False, server_default="hh"),
        sa.Column("source_host", sa.String(40), nullable=False, server_default="hh.ru"),
        sa.Column("search_text", sa.String(500), nullable=False),
        sa.Column("area_ids", json_type(), nullable=False, server_default="[]"),
        sa.Column("polling_interval_seconds", sa.Integer(), nullable=False, server_default="900"),
        sa.Column("include_keywords", json_type(), nullable=False, server_default="[]"),
        sa.Column("exclude_keywords", json_type(), nullable=False, server_default="[]"),
        sa.Column("required_keywords", json_type(), nullable=False, server_default="[]"),
        sa.Column("excluded_companies", json_type(), nullable=False, server_default="[]"),
        sa.Column("employment_types", json_type(), nullable=False, server_default="[]"),
        sa.Column("schedules", json_type(), nullable=False, server_default="[]"),
        sa.Column("experience_levels", json_type(), nullable=False, server_default="[]"),
        sa.Column("salary_min", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(12)),
        sa.Column("only_with_salary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notification_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("include_min_matches", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("baseline_started_at", sa.DateTime(timezone=True)),
        sa.Column("baseline_completed_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("name", name="uq_search_profiles_name"),
    )
    op.create_index("ix_search_profiles_name", "search_profiles", ["name"])
    op.create_index("ix_search_profiles_next_run_at", "search_profiles", ["next_run_at"])

    op.create_table(
        "vacancies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("alternate_url", sa.String(2000)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("employer_name", sa.String(500)),
        sa.Column("employer_external_id", sa.String(120)),
        sa.Column("area", sa.String(300)),
        sa.Column("area_id", sa.String(80)),
        sa.Column("city", sa.String(300)),
        sa.Column("salary_from", sa.Numeric(14, 2)),
        sa.Column("salary_to", sa.Numeric(14, 2)),
        sa.Column("salary_currency", sa.String(12)),
        sa.Column("salary_gross", sa.Boolean()),
        sa.Column("experience", sa.String(120)),
        sa.Column("experience_id", sa.String(80)),
        sa.Column("employment", sa.String(120)),
        sa.Column("employment_id", sa.String(80)),
        sa.Column("schedule", sa.String(120)),
        sa.Column("schedule_id", sa.String(80)),
        sa.Column("description", sa.Text()),
        sa.Column("key_skills", json_type(), nullable=False, server_default="[]"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("raw_payload", json_type(), nullable=False, server_default="{}"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("source", "external_id", name="uq_vacancy_source_external"),
    )
    op.create_index("ix_vacancies_content_hash", "vacancies", ["content_hash"])

    op.create_table(
        "search_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notified_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text()),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_search_runs_profile_started", "search_runs", ["search_profile_id", "started_at"]
    )

    op.create_table(
        "match_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vacancy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vacancies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "search_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "search_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("match_reasons", json_type(), nullable=False, server_default="[]"),
        sa.Column("reject_reasons", json_type(), nullable=False, server_default="[]"),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "notification_status", sa.String(30), nullable=False, server_default="not_requested"
        ),
        sa.Column("notification_error", sa.Text()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("vacancy_id", "search_profile_id", name="uq_match_vacancy_profile"),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vacancy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vacancies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_profiles.id", ondelete="SET NULL"),
        ),
        sa.Column("recipient_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("telegram_message_id", sa.Integer()),
        sa.Column("last_error", sa.Text()),
        sa.Column("unknown_delivery", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("vacancy_id", "recipient_key", name="uq_delivery_vacancy_recipient"),
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("match_results")
    op.drop_index("ix_search_runs_profile_started", table_name="search_runs")
    op.drop_table("search_runs")
    op.drop_index("ix_vacancies_content_hash", table_name="vacancies")
    op.drop_table("vacancies")
    op.drop_index("ix_search_profiles_next_run_at", table_name="search_profiles")
    op.drop_index("ix_search_profiles_name", table_name="search_profiles")
    op.drop_table("search_profiles")
