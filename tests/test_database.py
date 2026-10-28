from datetime import UTC, datetime
from decimal import Decimal

from app.models.entities import NotificationDelivery, SearchProfile, SearchRun
from app.providers.base import JobDTO
from app.services.monitoring import upsert_vacancy
from sqlalchemy import select


def dto(title: str = "Горный инженер") -> JobDTO:
    return JobDTO(
        source="hh",
        external_id="42",
        source_url="https://hh.kz/vacancy/42",
        title=title,
        employer_name="Рудник",
        area="Караганда",
        area_id="160",
        city="Караганда",
        salary_from=Decimal("500000"),
        salary_to=Decimal("650000"),
        salary_currency="KZT",
        description="Планирование работ",
        key_skills=["Micromine"],
        published_at=datetime.now(UTC),
    )


async def test_duplicate_vacancy_updates_existing(db_session) -> None:
    first, is_new, changed = await upsert_vacancy(db_session, dto())
    await db_session.commit()
    second, second_new, second_changed = await upsert_vacancy(
        db_session, dto("Обновленный горный инженер")
    )
    await db_session.commit()
    assert first.id == second.id
    assert is_new is True
    assert second_new is False
    assert second_changed is True
    assert second.title == "Обновленный горный инженер"


async def test_notification_delivery_is_idempotent(db_session) -> None:
    profile = SearchProfile(name="p", search_text="x")
    db_session.add(profile)
    await db_session.flush()
    run = SearchRun(search_profile_id=profile.id, status="success")
    db_session.add(run)
    await db_session.flush()
    vacancy, _, _ = await upsert_vacancy(db_session, dto())
    await db_session.commit()
    delivery = NotificationDelivery(vacancy_id=vacancy.id, recipient_key="1", profile_id=profile.id)
    db_session.add(delivery)
    await db_session.commit()
    duplicate = NotificationDelivery(
        vacancy_id=vacancy.id, recipient_key="1", profile_id=profile.id
    )
    db_session.add(duplicate)
    try:
        await db_session.commit()
    except Exception:
        await db_session.rollback()
    rows = list(await db_session.scalars(select(NotificationDelivery)))
    assert len(rows) == 1
