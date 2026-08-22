from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from dedektif_osint.gui import MainWindow


def test_gui_builds_valid_bounded_config() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.usernames.setText("alice, bob")
    window.acknowledge.setChecked(True)
    config = window._config()
    assert config.usernames == ("alice", "bob")
    assert config.concurrency == 4
    window.close()
    app.processEvents()
