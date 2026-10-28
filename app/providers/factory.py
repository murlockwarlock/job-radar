from typing import Any

from app.providers.base import BaseJobProvider
from app.providers.hh import HHProvider


def build_provider(source: str, client: Any | None = None) -> BaseJobProvider:
    if source == "hh":
        return HHProvider(client)
    raise ValueError(f"Unsupported job source: {source}")
