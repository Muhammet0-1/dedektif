from __future__ import annotations

import asyncio

import pytest

from dedektif_osint.catalog import PLATFORMS
from dedektif_osint.errors import TransportError
from dedektif_osint.models import HTTPObservation
from dedektif_osint.transport import USER_AGENT, AioHttpTransport


def test_user_agent_is_descriptive() -> None:
    assert USER_AGENT.startswith("Dedektif/")
    assert "Mozilla" not in USER_AGENT


def test_transport_rejects_non_allowlisted_host_before_io() -> None:
    transport = AioHttpTransport(timeout=2, concurrency=1)
    transport._session = object()  # type: ignore[assignment]
    with pytest.raises(TransportError, match="allowlist"):
        asyncio.run(transport.request(PLATFORMS[0], "https://example.invalid/users/alice"))


class FakeContent:
    async def read(self, size: int) -> bytes:
        assert size == 1
        return b"x"


class FakeResponse:
    def __init__(self) -> None:
        self.status = 302
        self.headers = {"Location": "https://other.example/"}
        self.content = FakeContent()

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        del args


class FakeSession:
    def get(self, url: str, *, allow_redirects: bool) -> FakeResponse:
        assert url == "https://api.github.com/users/alice"
        assert allow_redirects is False
        return FakeResponse()


def test_transport_never_follows_redirects_and_retains_only_metadata() -> None:
    transport = AioHttpTransport(timeout=2, concurrency=1)
    transport._session = FakeSession()  # type: ignore[assignment]
    observation = asyncio.run(transport.request(PLATFORMS[0], "https://api.github.com/users/alice"))
    assert observation == HTTPObservation(302, "https://other.example/")
