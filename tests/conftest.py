"""Test isolation: fail if a unit test attempts real network or subprocess access."""

from __future__ import annotations

import socket
import subprocess
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def block_external_io(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    def blocked(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("external I/O is forbidden in tests")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)
    monkeypatch.setattr(subprocess, "call", blocked)
    monkeypatch.setattr(subprocess, "check_call", blocked)
    monkeypatch.setattr(subprocess, "check_output", blocked)
    yield
