"""Empty plotting workspace for the tabbed UI foundation."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class GraphsWidget(QWidget):
    """Present a restrained empty state until plotting is implemented."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphsWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch()

        self.empty_label = QLabel("No channels are currently plotted.")
        self.empty_label.setObjectName("graphsEmptyLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        detail = QLabel("Live plotting will be added in the next milestone.")
        detail.setObjectName("graphsEmptyDetail")
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(detail)
        layout.addStretch()
