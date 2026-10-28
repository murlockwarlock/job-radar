from app.models.entities import SearchProfile
from app.services.profiles import seed_profiles


async def test_seed_profile_created_only_once(db_session) -> None:
    first = await seed_profiles(db_session)
    second = await seed_profiles(db_session)
    assert isinstance(first, SearchProfile)
    assert first.name == "Mining Kazakhstan"
    assert first.polling_interval_seconds == 900
    assert first.area_ids == ["40"]
    assert second is None
