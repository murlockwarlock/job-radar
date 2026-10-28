from types import SimpleNamespace

from app.notifications.telegram import TelegramNotifier, format_vacancy_message


def test_telegram_message_escapes_html() -> None:
    vacancy = SimpleNamespace(
        title="<script>",
        employer_name="A & B",
        city="Караганда",
        area=None,
        schedule="Вахта",
        salary_from=500000,
        salary_to=650000,
        salary_currency="KZT",
        experience="3–6 лет",
        source_url="https://hh.kz/vacancy/1",
        source="hh",
    )
    message = format_vacancy_message(vacancy, ["горный инженер"], "Mining Kazakhstan")
    assert "&lt;script&gt;" in message
    assert "A &amp; B" in message
    assert "Открыть" not in message


async def test_telegram_notifier_uses_mock_bot(monkeypatch) -> None:
    class Session:
        async def close(self) -> None:
            return None

    class FakeBot:
        def __init__(self, **_: object) -> None:
            self.session = Session()

        async def send_message(self, **_: object) -> SimpleNamespace:
            return SimpleNamespace(message_id=17)

    monkeypatch.setattr("app.notifications.telegram.Bot", FakeBot)
    vacancy = SimpleNamespace(
        title="Горный инженер",
        employer_name="Рудник",
        city="Караганда",
        area=None,
        schedule="Вахта",
        salary_from=None,
        salary_to=None,
        salary_currency=None,
        experience=None,
        source_url="https://hh.kz/vacancy/1",
        source="hh",
    )
    message_id = await TelegramNotifier("token", 123).send(vacancy, SimpleNamespace())
    assert message_id == 17
