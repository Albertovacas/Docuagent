from dataclasses import dataclass
from typing import Any


@dataclass
class SearchResult:
    text: str
    metadata: dict[str, Any]
    score: float | None = None


@dataclass
class Evidence:
    text: str
    source: str | None
    page: int | None
    score: float | None = None
