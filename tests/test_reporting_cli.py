from __future__ import annotations

import json

import pytest

from dedektif_osint.cli import main
from dedektif_osint.models import CheckResult, CheckState, SearchReport
from dedektif_osint.reporting import escape_terminal, render


def sample_report() -> SearchReport:
    return SearchReport(
        (
            CheckResult(
                "alice",
                "github",
                "GitHub",
                "development",
                "https://api.github.com/users/alice",
                CheckState.FOUND,
                200,
                "success",
                12,
            ),
        )
    )


def test_terminal_controls_are_escaped() -> None:
    assert escape_terminal("safe\x1b[31m") == "safe\\x1b[31m"


def test_text_report_contains_summary() -> None:
    output = render(sample_report(), "text")
    assert "FOUND" in output
    assert "Candidate profiles: 1" in output


def test_json_report_is_strict_and_round_trips() -> None:
    data = json.loads(render(sample_report(), "json"))
    assert data["summary"] == {"checks": 1, "candidates": 1}
    assert data["results"][0]["state"] == "found"


def test_jsonl_has_one_record_per_result() -> None:
    lines = render(sample_report(), "jsonl").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["platform_key"] == "github"


def test_unknown_format_is_rejected() -> None:
    with pytest.raises(ValueError):
        render(sample_report(), "yaml")


def test_cli_self_test_is_networkless(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["self-test"]) == 0
    assert json.loads(capsys.readouterr().out)["network_used"] is False


def test_cli_catalog_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["catalog", "--format", "json"]) == 0
    records = json.loads(capsys.readouterr().out)
    assert records[0]["key"] == "github"
    assert len(records) == 9


def test_cli_requires_acknowledgement(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["check", "alice"])
    assert exc_info.value.code == 2
    assert "acknowledgement" in capsys.readouterr().err
