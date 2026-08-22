from __future__ import annotations

import asyncio

import pytest

from dedektif_osint.catalog import PLATFORMS
from dedektif_osint.config import SearchConfig
from dedektif_osint.engine import classify, search
from dedektif_osint.errors import TransportError
from dedektif_osint.models import CheckState, HTTPObservation, Platform


class FakeTransport:
    def __init__(self, statuses: dict[str, int] | None = None) -> None:
        self.statuses = statuses or {}
        self.calls: list[tuple[str, str]] = []

    async def request(self, platform: Platform, url: str) -> HTTPObservation:
        self.calls.append((platform.key, url))
        return HTTPObservation(self.statuses.get(platform.key, 404))


class FailingTransport:
    async def request(self, platform: Platform, url: str) -> HTTPObservation:
        del platform, url
        raise TransportError("TimeoutError")


class ConcurrencyTransport:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0

    async def request(self, platform: Platform, url: str) -> HTTPObservation:
        del platform, url
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        await asyncio.sleep(0.001)
        self.active -= 1
        return HTTPObservation(404)


@pytest.mark.parametrize(
    ("status", "state"),
    [
        (200, CheckState.FOUND),
        (204, CheckState.FOUND),
        (404, CheckState.NOT_FOUND),
        (410, CheckState.NOT_FOUND),
        (301, CheckState.UNKNOWN),
        (401, CheckState.UNKNOWN),
        (403, CheckState.UNKNOWN),
        (429, CheckState.UNKNOWN),
        (500, CheckState.UNKNOWN),
    ],
)
def test_classifies_conservatively(status: int, state: CheckState) -> None:
    assert classify(HTTPObservation(status))[0] is state


def test_search_uses_only_selected_catalog_and_sorts_results() -> None:
    transport = FakeTransport({"github": 200, "gitlab": 404})
    config = SearchConfig(
        ("Bob", "alice"),
        True,
        categories=("development",),
        request_delay=0,
    )
    report = asyncio.run(search(config, transport=transport))
    assert len(transport.calls) == 4
    assert [result.username for result in report.results] == ["alice", "alice", "Bob", "Bob"]
    assert report.candidate_count == 2


def test_transport_failure_becomes_structured_error() -> None:
    config = SearchConfig(
        ("alice",),
        True,
        categories=("development",),
        request_delay=0,
    )
    report = asyncio.run(search(config, transport=FailingTransport()))
    assert {result.state for result in report.results} == {CheckState.ERROR}
    assert all(result.status is None for result in report.results)
    assert all("TimeoutError" in result.reason for result in report.results)


def test_cancelled_search_dispatches_nothing() -> None:
    transport = FakeTransport()
    config = SearchConfig(("alice",), True, request_delay=0)
    report = asyncio.run(search(config, transport=transport, cancelled=lambda: True))
    assert report.results == ()
    assert transport.calls == []


def test_progress_callback_receives_completed_checks() -> None:
    events: list[tuple[int, int, str]] = []
    config = SearchConfig(
        ("alice",),
        True,
        categories=("development",),
        request_delay=0,
    )
    asyncio.run(
        search(
            config,
            transport=FakeTransport(),
            progress=lambda done, total, result: events.append((done, total, result.platform_key)),
        )
    )
    assert [event[0] for event in events] == [1, 2]
    assert all(event[1] == 2 for event in events)


def test_runtime_concurrency_never_exceeds_configured_limit() -> None:
    transport = ConcurrencyTransport()
    config = SearchConfig(("alice",), True, concurrency=2, request_delay=0)
    asyncio.run(search(config, transport=transport))
    assert transport.maximum_active == 2


def test_profile_url_uses_percent_encoding_defensively() -> None:
    platform = PLATFORMS[0]
    assert platform.profile_url("alice") == "https://api.github.com/users/alice"
