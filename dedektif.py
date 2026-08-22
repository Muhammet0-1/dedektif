#!/usr/bin/env python3
"""Compatibility launcher for the optional desktop interface."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    source_root = Path(__file__).resolve().parent / "src"
    if source_root.is_dir():
        sys.path.insert(0, str(source_root))

from dedektif_osint.gui_main import main

raise SystemExit(main())
