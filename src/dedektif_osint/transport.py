"""Verified-TLS, no-proxy, no-redirect HTTP transport."""

from __future__ import annotations

import asyncio
import ssl
from types import TracebackType
from typing import Protocol
from urllib.parse import urlsplit

import aiohttp

from .errors import TransportError
from .models import HTTPObservation, Platform

USER_AGENT = "Dedektif/3.0 (+https://github.com/Muhammet0-1/dedektif)"


class Transport(Protocol):
    async def request(self, platform: Platform, url: str) -> HTTPObservation: ...


class AioHttpTransport:
    """Retain status metadata only; response bodies are never stored."""

    def __init__(self, *, timeout: float, concurrency: int) -> None:
        self._timeout = timeout
        self._concurrency = concurrency
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> AioHttpTransport:
        context = ssl.create_default_context()
        connector = aiohttp.TCPConnector(
            ssl=context,
            limit=self._concurrency,
            ttl_dns_cache=60,
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            cookie_jar=aiohttp.DummyCookieJar(),
            timeout=aiohttp.ClientTimeout(total=self._timeout),
            trust_env=False,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9"},
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def request(self, platform: Platform, url: str) -> HTTPObservation:
        session = self._session
        if session is None:
            raise RuntimeError("transport is not open")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != platform.host:
            raise TransportError("catalog URL failed its HTTPS host allowlist")
        try:
            async with session.get(url, allow_redirects=False) as response:
                await response.content.read(1)
                return HTTPObservation(
                    status=response.status,
                    location=response.headers.get("Location"),
                )
        except asyncio.CancelledError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
            raise TransportError(type(exc).__name__) from exc
