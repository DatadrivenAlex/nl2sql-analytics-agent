"""Values passed between the generator, the executor, and the API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class GeneratedSQL:
    sql: str
    explanation: str
    source: str


@dataclass(frozen=True)
class AskAnswer:
    question: str
    sql: str
    explanation: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
