from __future__ import annotations

import pytest

from dedektif_osint.catalog import CATEGORIES, PLATFORMS, select_platforms
from dedektif_osint.config import MAX_USERNAMES, SearchConfig, normalize_usernames
from dedektif_osint.errors import ConfigurationError


def test_catalog_is_https_and_hosts_match() -> None:
    assert len(PLATFORMS) == 9
    assert len({platform.key for platform in PLATFORMS}) == len(PLATFORMS)
    for platform in PLATFORMS:
        url = platform.profile_url("valid_user")
        assert url.startswith(f"https://{platform.host}/")
        assert "valid_user" in url


def test_category_selection_is_deterministic() -> None:
    selected = select_platforms(("development",))
    assert [platform.key for platform in selected] == ["github", "gitlab"]
    assert tuple(sorted(CATEGORIES)) == CATEGORIES


@pytest.mark.parametrize(
    "username",
    ["a", "Alpha_01", "a.b-c", "x" * 39],
)
def test_accepts_safe_ascii_usernames(username: str) -> None:
    assert normalize_usernames((username,)) == (username,)


@pytest.mark.parametrize(
    "username",
    ["", "-leading", "trailing-", "a/b", "with space", "üser", "x" * 40],
)
def test_rejects_ambiguous_usernames(username: str) -> None:
    with pytest.raises(ConfigurationError):
        normalize_usernames((username,))


def test_deduplicates_case_insensitively() -> None:
    assert normalize_usernames(("Alice", " alice ", "Bob")) == ("Alice", "Bob")


def test_rejects_more_than_five_usernames() -> None:
    with pytest.raises(ConfigurationError, match="at most"):
        normalize_usernames(tuple(f"user{index}" for index in range(MAX_USERNAMES + 1)))


def test_requires_exact_boolean_acknowledgement() -> None:
    with pytest.raises(ConfigurationError, match="acknowledgement"):
        SearchConfig(("alice",), acknowledge_public_data=False)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timeout", 0.9),
        ("timeout", 20.1),
        ("concurrency", 0),
        ("concurrency", 5),
        ("request_delay", -0.1),
        ("request_delay", 1.1),
    ],
)
def test_rejects_unbounded_numeric_settings(field: str, value: float) -> None:
    kwargs: dict[str, object] = {
        "usernames": ("alice",),
        "acknowledge_public_data": True,
        field: value,
    }
    with pytest.raises(ConfigurationError):
        SearchConfig(**kwargs)  # type: ignore[arg-type]


def test_rejects_unknown_category() -> None:
    with pytest.raises(ConfigurationError, match="unknown categories"):
        SearchConfig(("alice",), True, categories=("secret",))


def test_request_count_is_strictly_bounded() -> None:
    config = SearchConfig(tuple(f"user{index}" for index in range(5)), True)
    assert config.request_count == 45
