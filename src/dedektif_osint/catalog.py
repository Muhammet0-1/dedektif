"""Small, reviewable catalog of public HTTPS profile endpoints."""

from __future__ import annotations

from .models import Platform

PLATFORMS: tuple[Platform, ...] = (
    Platform(
        "github",
        "GitHub",
        "development",
        "https://api.github.com/users/{username}",
        "api.github.com",
    ),
    Platform("gitlab", "GitLab", "development", "https://gitlab.com/{username}", "gitlab.com"),
    Platform(
        "reddit",
        "Reddit",
        "social",
        "https://www.reddit.com/user/{username}/about.json",
        "www.reddit.com",
    ),
    Platform("twitch", "Twitch", "social", "https://www.twitch.tv/{username}", "www.twitch.tv"),
    Platform(
        "steam",
        "Steam Community",
        "gaming",
        "https://steamcommunity.com/id/{username}",
        "steamcommunity.com",
    ),
    Platform("medium", "Medium", "publishing", "https://medium.com/@{username}", "medium.com"),
    Platform("telegram", "Telegram", "social", "https://t.me/{username}", "t.me"),
    Platform(
        "pastebin", "Pastebin", "publishing", "https://pastebin.com/u/{username}", "pastebin.com"
    ),
    Platform(
        "wikipedia",
        "Wikipedia",
        "knowledge",
        "https://en.wikipedia.org/wiki/User:{username}",
        "en.wikipedia.org",
    ),
)

CATEGORIES: tuple[str, ...] = tuple(sorted({platform.category for platform in PLATFORMS}))


def select_platforms(categories: tuple[str, ...]) -> tuple[Platform, ...]:
    """Return the complete catalog or the requested category subset."""

    if not categories:
        return PLATFORMS
    selected = frozenset(categories)
    return tuple(platform for platform in PLATFORMS if platform.category in selected)
