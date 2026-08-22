"""Optional PyQt5 desktop interface backed by the same bounded engine."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .catalog import CATEGORIES
from .config import SearchConfig
from .engine import search
from .errors import ConfigurationError
from .models import CheckResult, SearchReport


class SearchWorker(QThread):
    progress = pyqtSignal(int, int, object)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, config: SearchConfig) -> None:
        super().__init__()
        self._config = config
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            report = asyncio.run(
                search(
                    self._config,
                    cancelled=self._cancelled.is_set,
                    progress=lambda done, total, result: self.progress.emit(done, total, result),
                )
            )
        except Exception as exc:  # Qt thread boundary: report a sanitized type only.
            self.failed.emit(type(exc).__name__)
            return
        self.completed.emit(report)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._worker: SearchWorker | None = None
        self._close_when_finished = False
        self.setWindowTitle("Dedektif — Public Profile OSINT")
        self.resize(980, 640)

        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.addWidget(QLabel("Kullanıcı adları (virgülle ayırın, en fazla 5):"))
        self.usernames = QLineEdit()
        self.usernames.setPlaceholderText("örnek, ikinci_kullanici")
        layout.addWidget(self.usernames)

        options = QHBoxLayout()
        self.category = QComboBox()
        self.category.addItem("Tüm kategoriler", "")
        for category in CATEGORIES:
            self.category.addItem(category, category)
        options.addWidget(QLabel("Kategori:"))
        options.addWidget(self.category)

        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(1.0, 20.0)
        self.timeout.setValue(8.0)
        options.addWidget(QLabel("Zaman aşımı:"))
        options.addWidget(self.timeout)

        self.concurrency = QSpinBox()
        self.concurrency.setRange(1, 4)
        self.concurrency.setValue(4)
        options.addWidget(QLabel("Eşzamanlılık:"))
        options.addWidget(self.concurrency)
        layout.addLayout(options)

        self.acknowledge = QCheckBox(
            "Yalnızca hukuka ve platform koşullarına uygun kamusal verileri kontrol edeceğim."
        )
        layout.addWidget(self.acknowledge)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Kontrolü başlat")
        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setEnabled(False)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Kullanıcı", "Platform", "Kategori", "Durum", "HTTP", "Profil URL"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        self.setCentralWidget(root)
        self.statusBar().showMessage(
            "Sonuçlar yalnızca HTTP sinyalidir; kimlik veya hesap sahipliği kanıtı değildir."
        )
        self.start_button.clicked.connect(self.start_search)
        self.cancel_button.clicked.connect(self.cancel_search)

    def _config(self) -> SearchConfig:
        usernames = tuple(part.strip() for part in self.usernames.text().split(","))
        selected = str(self.category.currentData())
        return SearchConfig(
            usernames=usernames,
            acknowledge_public_data=self.acknowledge.isChecked(),
            categories=(selected,) if selected else (),
            timeout=float(self.timeout.value()),
            concurrency=int(self.concurrency.value()),
        )

    def start_search(self) -> None:
        try:
            config = self._config()
        except ConfigurationError as exc:
            QMessageBox.warning(self, "Geçersiz yapılandırma", str(exc))
            return
        self.table.setRowCount(0)
        self.progress_bar.setRange(0, config.request_count)
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        worker = SearchWorker(config)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        worker.start()

    def cancel_search(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.cancel_button.setEnabled(False)
            self.statusBar().showMessage("İptal isteniyor…")

    def _on_progress(self, done: int, total: int, result: Any) -> None:
        if not isinstance(result, CheckResult):
            return
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = (
            result.username,
            result.platform_name,
            result.category,
            result.state.value,
            "-" if result.status is None else str(result.status),
            result.profile_url,
        )
        for column, value in enumerate(values):
            self.table.setItem(row, column, QTableWidgetItem(value))

    def _on_completed(self, report: Any) -> None:
        if isinstance(report, SearchReport):
            self.statusBar().showMessage(
                f"Tamamlandı: {len(report.results)} kontrol, {report.candidate_count} aday profil."
            )

    def _on_failed(self, error_type: str) -> None:
        QMessageBox.critical(
            self, "Kontrol başarısız", f"Beklenen ağ işlemi tamamlanamadı: {error_type}"
        )

    def _on_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._worker = None
        if self._close_when_finished:
            self.close()

    def closeEvent(self, event: Any) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._close_when_finished = True
            self.statusBar().showMessage("Güvenli kapanış için etkin istekler bekleniyor…")
            event.ignore()
            return
        event.accept()


def main() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return int(app.exec_())
