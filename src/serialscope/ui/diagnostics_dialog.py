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
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
        self.setMinimumSize(620, 420)
        self.resize(720, 620)
        self._hub = hub
        self._sources = sources
        self._replay = replay_diagnostics
        self._on_settings_changed = on_settings_changed

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 12)
        outer.setSpacing(10)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source"))
        self.source_combo = QComboBox()
        self.source_combo.setObjectName("diagnosticsSourceCombo")
        self.source_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.source_combo.setMinimumContentsLength(18)
        self.source_combo.currentIndexChanged.connect(self._refresh)
        source_row.addWidget(self.source_combo, 1)
        layout.addLayout(source_row)

        status = QGroupBox("Status")
        grid = QGridLayout(status)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)
        self.status_value = self._status_label("Disconnected")
        self.uptime_value = self._status_label("—")
        self.last_data_value = self._status_label("—")
        self.rx_rate_value = self._status_label("—")
        self.messages_value = self._status_label("0")
        self.structured_value = self._status_label("0")
        self.parser_errors_value = self._status_label("0")
        self.success_value = self._status_label("—")
        self.reconnects_value = self._status_label("0")
        self.longest_gap_value = self._status_label("—")
        metrics = (
            ("State", self.status_value, "Uptime", self.uptime_value),
            ("Last data", self.last_data_value, "RX rate", self.rx_rate_value),
            ("Messages", self.messages_value, "Structured", self.structured_value),
            ("Parser errors", self.parser_errors_value, "Success", self.success_value),
            ("Reconnects", self.reconnects_value, "Longest gap", self.longest_gap_value),
        )
        for row, (left_name, left_value, right_name, right_value) in enumerate(metrics):
            grid.addWidget(self._metric_caption(left_name), row, 0)
            grid.addWidget(left_value, row, 1)
            grid.addWidget(self._metric_caption(right_name), row, 2)
            grid.addWidget(right_value, row, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        layout.addWidget(status)

        channels = QGroupBox("Channels")
        channel_layout = QVBoxLayout(channels)
        channel_layout.setContentsMargins(8, 8, 8, 8)
        self.channel_table = QTableWidget(0, 7)
        self.channel_table.setObjectName("diagnosticsChannelTable")
        self.channel_table.setHorizontalHeaderLabels(
            ("Channel", "Rate", "Avg dt", "Max gap", "Age", "Jitter", "State")
        )
        self.channel_table.verticalHeader().setVisible(False)
        self.channel_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.channel_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.channel_table.setMinimumHeight(120)
        self.channel_table.setWordWrap(False)
        channel_header = self.channel_table.horizontalHeader()
        channel_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 7):
            channel_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        channel_layout.addWidget(self.channel_table)
        layout.addWidget(channels, 1)

        gaps = QGroupBox("Recent Data Gaps")
        gap_layout = QVBoxLayout(gaps)
        gap_layout.setContentsMargins(8, 8, 8, 8)
        self.gap_table = QTableWidget(0, 3)
        self.gap_table.setObjectName("diagnosticsGapTable")
        self.gap_table.setHorizontalHeaderLabels(("Start", "Duration", "Channel"))
        self.gap_table.verticalHeader().setVisible(False)
        self.gap_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.gap_table.setMaximumHeight(120)
        self.gap_table.setMinimumHeight(72)
        self.gap_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        gap_layout.addWidget(self.gap_table)
        layout.addWidget(gaps)

        settings = QGroupBox("Thresholds")
        settings_row = QHBoxLayout(settings)
        settings_row.setContentsMargins(10, 8, 10, 8)
        settings_row.setSpacing(8)
        self.stale_spin = QDoubleSpinBox()
        self.stale_spin.setRange(2.0, 20.0)
        self.stale_spin.setDecimals(1)
        self.stale_spin.setValue(hub.settings.stale_multiplier)
        self.stale_spin.setSuffix(" ×")
        self.stale_spin.setMaximumWidth(120)
        self.gap_spin = QDoubleSpinBox()
        self.gap_spin.setRange(2.0, 20.0)
        self.gap_spin.setDecimals(1)
        self.gap_spin.setValue(hub.settings.gap_multiplier)
        self.gap_spin.setSuffix(" ×")
        self.gap_spin.setMaximumWidth(120)
        self.expected_spin = QDoubleSpinBox()
        self.expected_spin.setRange(0.0, 3600.0)
        self.expected_spin.setDecimals(3)
        self.expected_spin.setSpecialValueText("Measured")
        self.expected_spin.setSuffix(" s")
        self.expected_spin.setValue(hub.settings.expected_interval_s or 0.0)
        self.expected_spin.setMaximumWidth(150)
        apply = QPushButton("Apply")
        apply.setObjectName("diagnosticsApplyThresholds")
        apply.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        apply.clicked.connect(self._apply_thresholds)
        settings_row.addWidget(self._metric_caption("Stale"))
        settings_row.addWidget(self.stale_spin)
        settings_row.addWidget(self._metric_caption("Gap"))
        settings_row.addWidget(self.gap_spin)
        settings_row.addWidget(self._metric_caption("Interval"))
        settings_row.addWidget(self.expected_spin)
        settings_row.addWidget(apply)
        settings_row.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("diagnosticsBodyScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        outer.addWidget(settings)

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
        outer.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)
        self.reload_sources()
        self._timer.start()

    @staticmethod
    def _metric_caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("mutedLabel")
        return label

    @staticmethod
    def _status_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("diagnosticsValue")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _fill_table(
        self,
        table: QTableWidget,
        rows: Sequence[tuple[str, ...]],
        *,
        center_from: int = 1,
    ) -> None:
        table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, text in enumerate(values):
                item = table.item(row, column)
                if item is None:
                    item = QTableWidgetItem(text)
                    if column >= center_from:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, column, item)
                elif item.text() != text:
                    item.setText(text)

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
            self.status_value.setText("No sources")
            self.uptime_value.setText("—")
            self.last_data_value.setText("—")
            self.rx_rate_value.setText("—")
            self.messages_value.setText("—")
            self.structured_value.setText("—")
            self.parser_errors_value.setText("—")
            self.success_value.setText("—")
            self.reconnects_value.setText("—")
            self.longest_gap_value.setText("—")
            self.channel_table.setRowCount(0)
            self.gap_table.setRowCount(0)
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
        self._fill_table(
            self.channel_table,
            tuple(
                (
                    channel.name,
                    _rate_text(channel.measured_rate_hz, "Hz"),
                    _optional_number(channel.average_interval_s, " s"),
                    _optional_number(channel.max_interval_s, " s"),
                    _optional_number(channel.last_update_age_s, " s"),
                    _optional_number(channel.jitter_s, " s"),
                    channel.state,
                )
                for channel in snapshot.channels
            ),
        )
        recent = tuple(snapshot.gaps)[-8:]
        self._fill_table(
            self.gap_table,
            tuple(
                (f"{gap.start_s:.2f}", f"{gap.duration_s:.2f} s", gap.channel or "Source")
                for gap in reversed(recent)
            ),
        )

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
        rows: list[tuple[str, ...]] = []
        for name, values in channels.items():
            payload = values if isinstance(values, dict) else {}
            rows.append(
                (
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
            )
        self._fill_table(self.channel_table, rows)

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
