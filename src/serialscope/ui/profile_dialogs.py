"""Compact built-in dialogs for Device Profile names."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)


class ProfileNameDialog(QDialog):
    """Collect one required, trimmed Device Profile name."""

    def __init__(
        self,
        title: str,
        initial_name: str = "",
        accept_text: str = "Save",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QFormLayout(self)
        self.name_input = QLineEdit(initial_name)
        self.name_input.setObjectName("profileNameInput")
        self.name_input.selectAll()
        layout.addRow("Name", self.name_input)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(accept_text)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(initial_name.strip())
        )
        self.name_input.textChanged.connect(
            lambda text: self.buttons.button(
                QDialogButtonBox.StandardButton.Ok
            ).setEnabled(bool(text.strip()))
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        self.name_input.setFocus()

    @property
    def profile_name(self) -> str:
        return self.name_input.text().strip()
