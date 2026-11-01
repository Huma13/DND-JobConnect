"""IJobSource: the interface every job source implements (SAD: Integration layer)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class SearchQuery:
    roles: tuple[str, ...]
    locations: tuple[str, ...] = ()
    max_results: int = 25


@dataclass
class RawPosting:
    platform: str
    external_id: str
    url: str
    title: str
    company: str
    location: str = ""
    description: str = ""
    posted_at: datetime | None = None
    skills: list[str] = field(default_factory=list)


class SourceError(Exception):
    """A source failed; the run records it and continues with other sources."""


class SourceRateLimited(SourceError):
    def __init__(self, message: str, retry_at: datetime | None = None):
        super().__init__(message)
        self.retry_at = retry_at


class IJobSource(Protocol):
    platform: str

    def search(self, query: SearchQuery) -> list[RawPosting]: ...
