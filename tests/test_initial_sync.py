from app.services.monitoring import should_enqueue_notification


def test_initial_sync_suppresses_notifications_by_default() -> None:
    assert should_enqueue_notification(True, True, True, False) is False
    assert should_enqueue_notification(True, True, False, False) is True


def test_initial_sync_can_be_enabled_explicitly() -> None:
    assert should_enqueue_notification(True, True, True, True) is True
    assert should_enqueue_notification(False, True, True, True) is False
