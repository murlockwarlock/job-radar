from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: str
    external_id: str
    source_url: str
    alternate_url: str | None = None
    title: str
    employer_name: str | None = None
    employer_external_id: str | None = None
    area: str | None = None
    area_id: str | None = None
    city: str | None = None
    salary_from: Decimal | None = None
    salary_to: Decimal | None = None
    salary_currency: str | None = None
    salary_gross: bool | None = None
    experience: str | None = None
    experience_id: str | None = None
    employment: str | None = None
    employment_id: str | None = None
    schedule: str | None = None
    schedule_id: str | None = None
    description: str | None = None
    key_skills: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    source_updated_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class BaseJobProvider(ABC):
    async def close(self) -> None:
        return None

    @abstractmethod
    def search(self, profile: Any) -> AsyncIterator[JobDTO]:
        raise NotImplementedError

    @abstractmethod
    async def get(self, external_id: str, host: str) -> JobDTO:
        raise NotImplementedError
