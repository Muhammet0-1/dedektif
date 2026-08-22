"""Bounded orchestration and conservative HTTP status classification."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from .config import SearchConfig
from .errors import TransportError
from .models import CheckResult, CheckState, HTTPObservation, Platform, SearchReport
from .transport import AioHttpTransport, Transport

ProgressCallback = Callable[[int, int, CheckResult], None]
CancelCheck = Callable[[], bool]


def classify(observation: HTTPObservation) -> tuple[CheckState, str]:
    """Classify conservatively; redirects and access controls remain unknown."""

    status = observation.status
    if 200 <= status < 300:
        return CheckState.FOUND, "public endpoint returned a success status"
    if status in {404, 410}:
        return CheckState.NOT_FOUND, "public endpoint reported no profile"
    if 300 <= status < 400:
        return CheckState.UNKNOWN, "redirect was not followed"
    if status in {401, 403, 429}:
        return CheckState.UNKNOWN, "endpoint restricted or rate limited the request"
    return CheckState.UNKNOWN, f"endpoint returned inconclusive HTTP status {status}"


async def _check_one(
    transport: Transport,
    platform: Platform,
    username: str,
    semaphore: asyncio.Semaphore,
    cancelled: CancelCheck,
) -> CheckResult:
    url = platform.profile_url(username)
    if cancelled():
        return CheckResult(
            username,
            platform.key,
            platform.name,
            platform.category,
            url,
            CheckState.CANCELLED,
            None,
            "search cancelled before dispatch",
            0,
        )
    started = time.monotonic()
    try:
        async with semaphore:
            if cancelled():
                return CheckResult(
                    username,
                    platform.key,
                    platform.name,
                    platform.category,
                    url,
                    CheckState.CANCELLED,
                    None,
                    "search cancelled before request",
                    max(0, round((time.monotonic() - started) * 1000)),
                )
            observation = await transport.request(platform, url)
        state, reason = classify(observation)
        status: int | None = observation.status
    except asyncio.CancelledError:
        raise
    except TransportError as exc:
        state = CheckState.ERROR
        reason = f"bounded HTTP observation failed ({exc})"
        status = None
    elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
    return CheckResult(
        username,
        platform.key,
        platform.name,
        platform.category,
        url,
        state,
        status,
        reason,
        elapsed_ms,
    )


async def _run(
    config: SearchConfig,
    transport: Transport,
    *,
    cancelled: CancelCheck,
    progress: ProgressCallback | None,
) -> SearchReport:
    semaphore = asyncio.Semaphore(config.concurrency)
    tasks: list[asyncio.Task[CheckResult]] = []
    for username in config.usernames:
        for platform in config.platforms:
            if cancelled():
                break
            if tasks and config.request_delay:
                await asyncio.sleep(config.request_delay)
            tasks.append(
                asyncio.create_task(_check_one(transport, platform, username, semaphore, cancelled))
            )
        if cancelled():
            break

    results: list[CheckResult] = []
    completed = 0
    try:
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            completed += 1
            if progress is not None:
                progress(completed, config.request_count, result)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

    results.sort(key=lambda item: (item.username.casefold(), item.platform_name.casefold()))
    return SearchReport(tuple(results))


async def search(
    config: SearchConfig,
    *,
    transport: Transport | None = None,
    cancelled: CancelCheck = lambda: False,
    progress: ProgressCallback | None = None,
) -> SearchReport:
    """Run a finite search, optionally with an injected offline transport."""

    if transport is not None:
        return await _run(
            config,
            transport,
            cancelled=cancelled,
            progress=progress,
        )
    async with AioHttpTransport(
        timeout=config.timeout,
        concurrency=config.concurrency,
    ) as live_transport:
        return await _run(
            config,
            live_transport,
            cancelled=cancelled,
            progress=progress,
        )
