"""Command-line interface for bounded public profile checks."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence

from . import __version__
from .catalog import CATEGORIES, PLATFORMS
from .config import SearchConfig
from .engine import search
from .errors import ConfigurationError, DedektifError
from .models import HTTPObservation, Platform
from .reporting import escape_terminal, render


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dedektif",
        description="Bounded public-profile OSINT checks with conservative results.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="check curated public profile endpoints")
    check.add_argument("usernames", nargs="+", metavar="USERNAME")
    check.add_argument(
        "--acknowledge-public-data",
        action="store_true",
        help="confirm lawful use of public data and applicable platform terms",
    )
    check.add_argument("--category", action="append", choices=CATEGORIES, default=[])
    check.add_argument("--timeout", type=float, default=8.0)
    check.add_argument("--concurrency", type=int, default=4)
    check.add_argument("--request-delay", type=float, default=0.20)
    check.add_argument("--format", choices=("text", "json", "jsonl"), default="text")
    check.add_argument(
        "--fail-on-found",
        action="store_true",
        help="return status 3 when a candidate profile is observed",
    )

    catalog = subparsers.add_parser("catalog", help="show the fixed endpoint catalog")
    catalog.add_argument("--format", choices=("text", "json"), default="text")
    subparsers.add_parser("self-test", help="run a deterministic test without network access")
    return parser


class _SelfTestTransport:
    async def request(self, platform: Platform, url: str) -> HTTPObservation:
        del url
        return HTTPObservation(200 if platform.key == "github" else 404)


def _run_self_test() -> int:
    config = SearchConfig(
        usernames=("example",),
        acknowledge_public_data=True,
        categories=("development",),
        request_delay=0.0,
    )
    report = asyncio.run(search(config, transport=_SelfTestTransport()))
    states = {result.platform_key: result.state.value for result in report.results}
    expected = {"github": "found", "gitlab": "not_found"}
    if states != expected:
        print("self-test failed", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "network_used": False}, sort_keys=True))
    return 0


def _show_catalog(output_format: str) -> int:
    records = [
        {
            "key": platform.key,
            "name": platform.name,
            "category": platform.category,
            "host": platform.host,
        }
        for platform in PLATFORMS
    ]
    if output_format == "json":
        print(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        for record in records:
            print(f"{record['key']:10} {record['category']:12} {record['name']} ({record['host']})")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "self-test":
        return _run_self_test()
    if args.command == "catalog":
        return _show_catalog(args.format)

    try:
        config = SearchConfig(
            usernames=tuple(args.usernames),
            acknowledge_public_data=args.acknowledge_public_data,
            categories=tuple(args.category),
            timeout=args.timeout,
            concurrency=args.concurrency,
            request_delay=args.request_delay,
        )
        report = asyncio.run(search(config))
    except ConfigurationError as exc:
        parser.error(escape_terminal(str(exc)))
    except (DedektifError, OSError) as exc:
        print(f"search failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("search cancelled", file=sys.stderr)
        return 130

    print(render(report, args.format))
    if args.fail_on_found and report.candidate_count:
        return 3
    return 0
