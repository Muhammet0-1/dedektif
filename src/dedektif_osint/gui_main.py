"""Optional GUI entry point with a clear missing-dependency error."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from .gui import main as gui_main
    except ImportError:
        print(
            "PyQt5 is required for the GUI; install with: pip install 'dedektif-osint[gui]'",
            file=sys.stderr,
        )
        return 2
    return gui_main()
