"""Immutable domain models used by the engine and presenters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import quote


class CheckState(str, Enum):
    """Conservative outcome of one public profile URL observation."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Platform:
    """A curated public HTTPS profile endpoint."""

    key: str
    name: str
    category: str
    url_template: str
    host: str

    def profile_url(self, username: str) -> str:
        return self.url_template.format(username=quote(username, safe=""))


@dataclass(frozen=True, slots=True)
class HTTPObservation:
    """Minimal metadata retained from one HTTP response."""

    status: int
    location: str | None = None


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One platform check result."""

    username: str
    platform_key: str
    platform_name: str
    category: str
    profile_url: str
    state: CheckState
    status: int | None
    reason: str
    elapsed_ms: int

    def to_dict(self) -> dict[str, object]:
        return {
            "username": self.username,
            "platform_key": self.platform_key,
            "platform_name": self.platform_name,
            "category": self.category,
            "profile_url": self.profile_url,
            "state": self.state.value,
            "status": self.status,
            "reason": self.reason,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass(frozen=True, slots=True)
class SearchReport:
    """Deterministically ordered results for one bounded search."""

    results: tuple[CheckResult, ...]

    @property
    def candidate_count(self) -> int:
        return sum(result.state is CheckState.FOUND for result in self.results)

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": {
                "checks": len(self.results),
                "candidates": self.candidate_count,
            },
            "results": [result.to_dict() for result in self.results],
        }
