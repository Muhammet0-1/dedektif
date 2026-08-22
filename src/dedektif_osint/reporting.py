"""Deterministic terminal-safe text and strict JSON reporting."""

from __future__ import annotations

import json

from .models import CheckResult, SearchReport


def escape_terminal(value: str) -> str:
    return "".join(char if char.isprintable() else f"\\x{ord(char):02x}" for char in value)


def _text_line(result: CheckResult) -> str:
    status = "-" if result.status is None else str(result.status)
    return (
        f"[{result.state.value.upper():9}] "
        f"{escape_terminal(result.username)} @ {escape_terminal(result.platform_name)} "
        f"HTTP={status} {escape_terminal(result.profile_url)}"
    )


def render(report: SearchReport, output_format: str) -> str:
    if output_format == "text":
        lines = [_text_line(result) for result in report.results]
        lines.append(
            f"Checks: {len(report.results)} | Candidate profiles: {report.candidate_count}"
        )
        return "\n".join(lines)
    if output_format == "json":
        return json.dumps(report.to_dict(), ensure_ascii=False, indent=2, allow_nan=False)
    if output_format == "jsonl":
        return "\n".join(
            json.dumps(result.to_dict(), ensure_ascii=False, allow_nan=False, sort_keys=True)
            for result in report.results
        )
    raise ValueError(f"unsupported output format: {output_format}")
