from app.api.routes import create_profile, run_profile_now, update_profile
from app.schemas.api import SearchProfileCreate, SearchProfileUpdate


async def test_profile_crud_and_manual_run(db_session, monkeypatch) -> None:
    profile = await create_profile(
        SearchProfileCreate(name="Backend", search_text="python", include_keywords=["python"]),
        db_session,
    )
    assert profile.name == "Backend"
    assert profile.next_run_at is not None

    updated = await update_profile(
        profile.id,
        SearchProfileUpdate(name="Python Backend", enabled=False),
        db_session,
    )
    assert updated.name == "Python Backend"
    assert updated.enabled is False

    calls: list[tuple[str, str]] = []

    class StubTask:
        def delay(self, profile_id: str, run_id: str) -> None:
            calls.append((profile_id, run_id))

    monkeypatch.setattr("app.api.routes.process_profile_task", StubTask())
    response = await run_profile_now(profile.id, db_session)
    assert response.status == "queued"
    assert calls == [(str(profile.id), str(response.run_id))]
