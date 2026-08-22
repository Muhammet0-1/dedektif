"""Validate the locally built wheel and source archive without installing them."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path


def main() -> int:
    wheels = list(Path("dist").glob("dedektif_osint-*.whl"))
    sdists = list(Path("dist").glob("dedektif_osint-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit("expected exactly one wheel and one sdist")

    with zipfile.ZipFile(wheels[0]) as archive:
        wheel_names = set(archive.namelist())
    required_wheel_suffixes = {
        "dedektif_osint/__init__.py",
        "dedektif_osint/cli.py",
        "dedektif_osint/engine.py",
        "dedektif_osint/gui.py",
        "dedektif_osint/py.typed",
    }
    if not required_wheel_suffixes.issubset(wheel_names):
        raise SystemExit("wheel is missing required package files")

    with tarfile.open(sdists[0], "r:gz") as archive:
        sdist_names = archive.getnames()
    required_sdist_suffixes = (
        "/tests/conftest.py",
        "/tests/test_engine.py",
        "/README.md",
        "/LICENSE",
        "/dedektif.py",
    )
    for suffix in required_sdist_suffixes:
        if not any(name.endswith(suffix) for name in sdist_names):
            raise SystemExit(f"sdist is missing {suffix}")
    print("package artifacts verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
