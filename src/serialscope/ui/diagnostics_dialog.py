"""Live data-quality diagnostics dialog."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from serialscope.diagnostics import (
    DiagnosticsHub,
    DiagnosticsSettings,
    SourceDiagnosticsSnapshot,
)


def _age_text(value: float | None) -> str:
    if value is None:
        return "—"
    if value < 1:
        return f"{value:.2f} s"
    if value < 60:
        return f"{value:.1f} s"
    minutes, seconds = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _rate_text(value: float | None, suffix: str) -> str:
    if value is None:
        return "—"
    if value >= 1000 and suffix == "B/s":
        return f"{value / 1000:.1f} kB/s"
    return f"{value:.2f} {suffix}"


def _optional_number(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:.3f}{suffix}"


class DiagnosticsDialog(QDialog):
    """Display throttled snapshots; does not own serial or logging state."""

    def __init__(
        self,
        hub: DiagnosticsHub,
        sources: Callable[[], Sequence[tuple[str, str]]],
        *,
        replay_diagnostics: dict[str, object] | None = None,
        on_settings_changed: Callable[[DiagnosticsSettings], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("diagnosticsDialog")
        self.setWindowTitle("Diagnostics")
        self.setMinimumSize(620, 480)
        self.resize(720, 560)
        self._hub = hub
        self._sources = sources
        self._replay = replay_diagnostics
        self._on_settings_changed = on_settings_changed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source"))
        self.source_combo = QComboBox()
        self.source_combo.setObjectName("diagnosticsSourceCombo")
        self.source_combo.currentIndexChanged.connect(self._refresh)
        source_row.addWidget(self.source_combo, 1)
        layout.addLayout(source_row)

        status = QGroupBox("Status")
        form = QFormLayout(status)
        self.status_value = QLabel("Disconnected")
        self.uptime_value = QLabel("—")
        self.last_data_value = QLabel("—")
        self.rx_rate_value = QLabel("—")
        self.messages_value = QLabel("0")
        self.structured_value = QLabel("0")
        self.parser_errors_value = QLabel("0")
        self.success_value = QLabel("—")
        self.reconnects_value = QLabel("0")
        self.longest_gap_value = QLabel("—")
        form.addRow("State", self.status_value)
        form.addRow("Uptime", self.uptime_value)
        form.addRow("Last data", self.last_data_value)
        form.addRow("RX rate", self.rx_rate_value)
        form.addRow("Messages", self.messages_value)
        form.addRow("Structured updates", self.structured_value)
        form.addRow("Parser errors", self.parser_errors_value)
        form.addRow("Parser success", self.success_value)
        form.addRow("Reconnects", self.reconnects_value)
        form.addRow("Longest source gap", self.longest_gap_value)
        layout.addWidget(status)

        channels = QGroupBox("Channels")
        channel_layout = QVBoxLayout(channels)
        self.channel_table = QTableWidget(0, 7)
        self.channel_table.setObjectName("diagnosticsChannelTable")
        self.channel_table.setHorizontalHeaderLabels(
            ("Channel", "Rate", "Avg dt", "Max gap", "Age", "Jitter", "State")
        )
        self.channel_table.verticalHeader().setVisible(False)
        self.channel_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.channel_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.channel_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        channel_layout.addWidget(self.channel_table)
        layout.addWidget(channels, 1)

        gaps = QGroupBox("Recent Data Gaps")
        gap_layout = QVBoxLayout(gaps)
        self.gap_table = QTableWidget(0, 3)
        self.gap_table.setObjectName("diagnosticsGapTable")
        self.gap_table.setHorizontalHeaderLabels(("Start (s)", "Duration", "Channel"))
        self.gap_table.verticalHeader().setVisible(False)
        self.gap_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.gap_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        gap_layout.addWidget(self.gap_table)
        layout.addWidget(gaps)

        settings = QGroupBox("Thresholds")
        settings_form = QFormLayout(settings)
        self.stale_spin = QDoubleSpinBox()
        self.stale_spin.setRange(2.0, 20.0)
        self.stale_spin.setDecimals(1)
        self.stale_spin.setValue(hub.settings.stale_multiplier)
        self.stale_spin.setSuffix(" ×")
        self.gap_spin = QDoubleSpinBox()
        self.gap_spin.setRange(2.0, 20.0)
        self.gap_spin.setDecimals(1)
        self.gap_spin.setValue(hub.settings.gap_multiplier)
        self.gap_spin.setSuffix(" ×")
        self.expected_spin = QDoubleSpinBox()
        self.expected_spin.setRange(0.0, 3600.0)
        self.expected_spin.setDecimals(3)
        self.expected_spin.setSpecialValueText("Measured")
        self.expected_spin.setSuffix(" s")
        self.expected_spin.setValue(hub.settings.expected_interval_s or 0.0)
        apply = QPushButton("Apply Thresholds")
        apply.setObjectName("diagnosticsApplyThresholds")
        apply.clicked.connect(self._apply_thresholds)
        settings_form.addRow("Stale after", self.stale_spin)
        settings_form.addRow("Gap after", self.gap_spin)
        settings_form.addRow("Expected interval", self.expected_spin)
        settings_form.addRow("", apply)
        layout.addWidget(settings)

        buttons = QHBoxLayout()
        reset = QPushButton("Reset Statistics")
        reset.setObjectName("diagnosticsResetButton")
        reset.clicked.connect(self._reset)
        copy = QPushButton("Copy Summary")
        copy.setObjectName("diagnosticsCopyButton")
        copy.clicked.connect(self._copy_summary)
        buttons.addWidget(reset)
        buttons.addWidget(copy)
        buttons.addStretch()
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        close.accepted.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)
        self.reload_sources()
        self._timer.start()

    def reload_sources(self) -> None:
        selected = self.source_combo.currentData()
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for source_id, name in self._sources():
            self.source_combo.addItem(name, source_id)
        index = self.source_combo.findData(selected)
        self.source_combo.setCurrentIndex(max(0, index))
        self.source_combo.blockSignals(False)
        self._refresh()

    def _selected_source_id(self) -> str | None:
        value = self.source_combo.currentData()
        return str(value) if value is not None else None

    def _refresh(self) -> None:
        source_id = self._selected_source_id()
        if source_id is None:
            return
        if self._replay is not None:
            self._show_replay(source_id)
            return
        snapshot = self._hub.live.snapshot(source_id)
        self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot: SourceDiagnosticsSnapshot) -> None:
        self.status_value.setText("Connected" if snapshot.connected else "Disconnected")
        self.uptime_value.setText(_age_text(snapshot.uptime_s))
        self.last_data_value.setText(
            "—" if snapshot.data_age_s is None else f"{snapshot.data_age_s:.2f} s ago"
        )
        self.rx_rate_value.setText(_rate_text(snapshot.rx_bytes_per_s, "B/s"))
        self.messages_value.setText(f"{snapshot.lines_received:,}")
        self.structured_value.setText(f"{snapshot.structured_updates:,}")
        self.parser_errors_value.setText(f"{snapshot.parser_errors:,}")
        if snapshot.parser_success_rate is None:
            self.success_value.setText("—")
        else:
            self.success_value.setText(f"{snapshot.parser_success_rate * 100:.1f}%")
        self.reconnects_value.setText(str(snapshot.reconnects))
        self.longest_gap_value.setText(_optional_number(snapshot.longest_gap_s, " s"))
        self.channel_table.setRowCount(len(snapshot.channels))
        for row, channel in enumerate(snapshot.channels):
            values = (
                channel.name,
                _rate_text(channel.measured_rate_hz, "Hz"),
                _optional_number(channel.average_interval_s, " s"),
                _optional_number(channel.max_interval_s, " s"),
                _optional_number(channel.last_update_age_s, " s"),
                _optional_number(channel.jitter_s, " s"),
                channel.state,
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.channel_table.setItem(row, column, item)
        recent = tuple(snapshot.gaps)[-8:]
        self.gap_table.setRowCount(len(recent))
        for row, gap in enumerate(reversed(recent)):
            self.gap_table.setItem(row, 0, QTableWidgetItem(f"{gap.start_s:.2f}"))
            self.gap_table.setItem(row, 1, QTableWidgetItem(f"{gap.duration_s:.2f} s"))
            self.gap_table.setItem(row, 2, QTableWidgetItem(gap.channel or "Source"))

    def _show_replay(self, source_id: str) -> None:
        sources = self._replay.get("sources") if isinstance(self._replay, dict) else None
        if not isinstance(sources, list):
            self.status_value.setText("No diagnostics available")
            return
        match = next(
            (
                item
                for item in sources
                if isinstance(item, dict) and item.get("source_id") == source_id
            ),
            sources[0] if sources and isinstance(sources[0], dict) else None,
        )
        if match is None:
            self.status_value.setText("No diagnostics available")
            return
        self.status_value.setText("Recorded session")
        self.structured_value.setText(str(match.get("structured_updates", "—")))
        self.parser_errors_value.setText(str(match.get("parser_errors", "—")))
        self.reconnects_value.setText(str(match.get("reconnects", "—")))
        gap = match.get("longest_gap_s")
        self.longest_gap_value.setText("—" if gap is None else f"{gap} s")
        channels = match.get("channels")
        if not isinstance(channels, dict):
            self.channel_table.setRowCount(0)
            return
        self.channel_table.setRowCount(len(channels))
        for row, (name, values) in enumerate(channels.items()):
            payload = values if isinstance(values, dict) else {}
            texts = (
                str(name),
                _rate_text(
                    float(payload["measured_rate_hz"])
                    if payload.get("measured_rate_hz") is not None
                    else None,
                    "Hz",
                ),
                _optional_number(
                    float(payload["average_interval_s"])
                    if payload.get("average_interval_s") is not None
                    else None,
                    " s",
                ),
                _optional_number(
                    float(payload["longest_gap_s"])
                    if payload.get("longest_gap_s") is not None
                    else None,
                    " s",
                ),
                "—",
                "—",
                "Recorded",
            )
            for column, text in enumerate(texts):
                self.channel_table.setItem(row, column, QTableWidgetItem(text))

    def _apply_thresholds(self) -> None:
        expected = self.expected_spin.value()
        settings = DiagnosticsSettings(
            stale_multiplier=self.stale_spin.value(),
            gap_multiplier=self.gap_spin.value(),
            expected_interval_s=None if expected <= 0 else expected,
        )
        self._hub.apply_settings(settings)
        if self._on_settings_changed is not None:
            self._on_settings_changed(settings)
        self._refresh()

    def _reset(self) -> None:
        if self._replay is not None:
            return
        self._hub.live.reset_live(self._selected_source_id())
        self._refresh()

    def _copy_summary(self) -> None:
        source_id = self._selected_source_id()
        if source_id is None:
            return
        snapshot = self._hub.live.snapshot(source_id)
        lines = [
            f"Source {snapshot.source_id}",
            f"State: {'Connected' if snapshot.connected else 'Disconnected'}",
            f"Structured updates: {snapshot.structured_updates}",
            f"Parser errors: {snapshot.parser_errors}",
            f"Reconnects: {snapshot.reconnects}",
        ]
        for channel in snapshot.channels:
            lines.append(
                f"{channel.name}: {channel.state} rate={channel.measured_rate_hz} age={channel.last_update_age_s}"
            )
        QApplication.clipboard().setText("\n".join(lines))

    def closeEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().closeEvent(event)
