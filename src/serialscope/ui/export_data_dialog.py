"""Compact options dialog for Selected Data CSV export."""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from serialscope.export import ALL_AVAILABLE, CURRENT_WINDOW


class ExportDataDialog(QDialog):
    """Choose whether to export the visible graph window or all retained data."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        live_history_limited: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("exportDataDialog")
        self.setWindowTitle("Export Selected Data")
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        range_group = QGroupBox("Range")
        range_layout = QVBoxLayout(range_group)
        self.window_radio = QRadioButton("Current graph time window")
        self.window_radio.setObjectName("exportRangeWindow")
        self.window_radio.setChecked(True)
        self.all_radio = QRadioButton("All retained data")
        self.all_radio.setObjectName("exportRangeAll")
        range_layout.addWidget(self.window_radio)
        range_layout.addWidget(self.all_radio)
        layout.addWidget(range_group)

        hint = QLabel(
            "CSV export writes actual stored measurements for the channels "
            "currently selected on Graphs. Smoothing and interpolation are "
            "not applied."
        )
        hint.setObjectName("exportDataHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        if live_history_limited:
            bound = QLabel(
                "Live history is limited to measurements currently retained "
                "in graph memory (up to one hour)."
            )
            bound.setObjectName("exportDataHistoryHint")
            bound.setWordWrap(True)
            layout.addWidget(bound)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("exportDataCancel")
        cancel.clicked.connect(self.reject)
        export = QPushButton("Export CSV")
        export.setObjectName("exportDataConfirm")
        export.setDefault(True)
        export.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(export)
        layout.addLayout(buttons)

    @property
    def range_mode(self) -> str:
        if self.window_radio.isChecked():
            return CURRENT_WINDOW
        return ALL_AVAILABLE
