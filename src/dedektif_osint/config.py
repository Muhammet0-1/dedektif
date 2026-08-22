"""Validated and bounded search configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .catalog import CATEGORIES, select_platforms
from .errors import ConfigurationError
from .models import Platform

_USERNAME_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,37}[A-Za-z0-9])?\Z")
MAX_USERNAMES = 5


def normalize_usernames(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Validate, de-duplicate, and preserve username order."""

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        username = raw.strip()
        if not _USERNAME_RE.fullmatch(username):
            raise ConfigurationError(
                f"invalid username {raw!r}; use 1-39 ASCII letters, digits, '.', '_' or '-'"
            )
        folded = username.casefold()
        if folded not in seen:
            normalized.append(username)
            seen.add(folded)
    if not normalized:
        raise ConfigurationError("at least one username is required")
    if len(normalized) > MAX_USERNAMES:
        raise ConfigurationError(f"at most {MAX_USERNAMES} usernames may be checked at once")
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class SearchConfig:
    """Fail-closed settings for a finite public-data check."""

    usernames: tuple[str, ...]
    acknowledge_public_data: bool
    categories: tuple[str, ...] = ()
    timeout: float = 8.0
    concurrency: int = 4
    request_delay: float = 0.20

    def __post_init__(self) -> None:
        object.__setattr__(self, "usernames", normalize_usernames(self.usernames))
        if self.acknowledge_public_data is not True:
            raise ConfigurationError(
                "explicit public-data authorization acknowledgement is required"
            )
        unknown = sorted(set(self.categories) - set(CATEGORIES))
        if unknown:
            raise ConfigurationError(f"unknown categories: {', '.join(unknown)}")
        if not 1.0 <= self.timeout <= 20.0:
            raise ConfigurationError("timeout must be between 1 and 20 seconds")
        if not 1 <= self.concurrency <= 4:
            raise ConfigurationError("concurrency must be between 1 and 4")
        if not 0.0 <= self.request_delay <= 1.0:
            raise ConfigurationError("request delay must be between 0 and 1 second")

    @property
    def platforms(self) -> tuple[Platform, ...]:
        return select_platforms(self.categories)

    @property
    def request_count(self) -> int:
        return len(self.usernames) * len(self.platforms)
