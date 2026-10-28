import httpx
from app.providers.hh import HHProvider


def test_hh_normalization() -> None:
    dto = HHProvider.normalize(
        {
            "id": "42",
            "name": "Горный инженер",
            "alternate_url": "https://hh.kz/vacancy/42",
            "description": "<p>Планирование&nbsp;работ</p>",
            "employer": {"id": "7", "name": "Рудник"},
            "area": {"id": "160", "name": "Караганда"},
            "salary": {"from": 500000, "to": 650000, "currency": "KZT", "gross": False},
            "experience": {"id": "between1And3", "name": "1–3 года"},
            "employment": {"id": "full", "name": "Полная занятость"},
            "schedule": {"id": "shift", "name": "Вахта"},
            "key_skills": [{"name": "Micromine"}],
        },
        "hh.kz",
    )
    assert dto.external_id == "42"
    assert dto.description == "Планирование работ"
    assert dto.salary_to == 650000
    assert dto.area_id == "160"


async def test_retry_on_transient_error() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"items": []}, request=request)

    provider = HHProvider(
        httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.hh.test")
    )
    assert await provider._request("/vacancies") == {"items": []}
    assert attempts == 2
    await provider.close()
