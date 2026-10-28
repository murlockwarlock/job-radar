import asyncio
import html
import logging
import re
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from app.core.config import get_settings
from app.providers.base import BaseJobProvider, JobDTO

logger = logging.getLogger(__name__)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = html.unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"\s+", " ", text).strip()


class HHProvider(BaseJobProvider):
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=settings.hh_api_base_url.rstrip("/"),
            timeout=settings.hh_request_timeout_seconds,
            headers={
                "Authorization": f"Bearer {settings.hh_access_token}"
                if settings.hh_access_token
                else "",
                "HH-User-Agent": settings.hh_user_agent,
                "User-Agent": settings.hh_user_agent,
                "Accept": "application/json",
            },
        )
        self.settings = settings
        if client is None and not settings.hh_access_token:
            raise RuntimeError("HH_ACCESS_TOKEN is required for HH API access")
        self._rate_lock = asyncio.Lock()
        self._last_request = 0.0

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _throttle(self) -> None:
        async with self._rate_lock:
            now = asyncio.get_running_loop().time()
            delay = self.settings.hh_min_request_interval_seconds - (now - self._last_request)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request = asyncio.get_running_loop().time()

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        await self._throttle()

        async def do_request() -> dict[str, Any]:
            response = await self.client.get(path, params=params)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    await asyncio.sleep(min(int(retry_after), 60))
                response.raise_for_status()
            if response.status_code >= 500:
                response.raise_for_status()
            if response.status_code in {401, 403}:
                raise RuntimeError(
                    "HH authorization failed; configure HH_ACCESS_TOKEN and HH_USER_AGENT"
                )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            wait=wait_random_exponential(multiplier=1, max=30),
            stop=stop_after_attempt(4),
            reraise=True,
        ):
            with attempt:
                try:
                    return await do_request()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code not in {429, 500, 502, 503, 504}:
                        raise
                    raise
        raise RuntimeError("unreachable")

    async def search(self, profile: Any) -> AsyncIterator[JobDTO]:
        if profile.source_host not in {"hh.ru", "hh.kz"}:
            raise ValueError("HH source host must be hh.ru or hh.kz")
        page = 0
        per_page = self.settings.hh_per_page
        while page < self.settings.hh_max_pages:
            params: dict[str, Any] = {
                "host": profile.source_host,
                "text": profile.search_text,
                "page": page,
                "per_page": per_page,
                "locale": "RU",
                "area": profile.area_ids,
                "period": 30,
            }
            if profile.only_with_salary:
                params["only_with_salary"] = "true"
            if profile.experience_levels:
                params["experience"] = profile.experience_levels
            if profile.employment_types:
                params["employment"] = profile.employment_types
            data = await self._request("/vacancies", params=params)
            items = data.get("items", [])
            for item in items:
                yield self.normalize(item, profile.source_host)
            pages = int(data.get("pages", page + 1))
            if page + 1 >= pages or not items:
                break
            page += 1

    async def get(self, external_id: str, host: str) -> JobDTO:
        if host not in {"hh.ru", "hh.kz"}:
            raise ValueError("HH source host must be hh.ru or hh.kz")
        return self.normalize(
            await self._request(f"/vacancies/{external_id}", params={"host": host}), host
        )

    @classmethod
    def normalize(cls, payload: dict[str, Any], host: str = "hh.ru") -> JobDTO:
        area = payload.get("area") or {}
        employer = payload.get("employer") or {}
        salary = payload.get("salary") or {}
        experience = payload.get("experience") or {}
        employment = payload.get("employment") or {}
        schedule = payload.get("schedule") or {}
        address = payload.get("address") or {}
        key_skills = [str(item.get("name", "")).strip() for item in payload.get("key_skills", [])]
        return JobDTO(
            source="hh",
            external_id=str(payload.get("id", "")),
            source_url=str(
                payload.get("alternate_url")
                or payload.get("url")
                or f"https://{host}/vacancy/{payload.get('id', '')}"
            ),
            alternate_url=payload.get("alternate_url"),
            title=str(payload.get("name") or "").strip(),
            employer_name=employer.get("name"),
            employer_external_id=str(employer["id"]) if employer.get("id") is not None else None,
            area=area.get("name"),
            area_id=str(area["id"]) if area.get("id") is not None else None,
            city=address.get("city") or area.get("name"),
            salary_from=Decimal(str(salary["from"])) if salary.get("from") is not None else None,
            salary_to=Decimal(str(salary["to"])) if salary.get("to") is not None else None,
            salary_currency=salary.get("currency"),
            salary_gross=salary.get("gross"),
            experience=experience.get("name"),
            experience_id=experience.get("id"),
            employment=employment.get("name"),
            employment_id=employment.get("id"),
            schedule=schedule.get("name"),
            schedule_id=schedule.get("id"),
            description=_strip_html(payload.get("description")),
            key_skills=[item for item in key_skills if item],
            published_at=_parse_datetime(payload.get("published_at")),
            source_updated_at=_parse_datetime(payload.get("updated_at")),
            raw_payload=payload,
        )
