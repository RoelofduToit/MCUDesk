"""Compact application preferences dialog."""

from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)

class PreferencesDialog(QDialog):
    """Edit preferences that benefit from explicit confirmation."""

    def __init__(
        self,
        current_theme: str,
        parent: QWidget | None = None,
        automatically_check_for_updates: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("preferencesDialog")
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        appearance = QGroupBox("Appearance")
        form = QFormLayout(appearance)
        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("themeCombo")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.setCurrentIndex(
            max(0, self.theme_combo.findData(current_theme))
        )
        form.addRow("Theme", self.theme_combo)
        layout.addWidget(appearance)

        updates = QGroupBox("Updates")
        updates_layout = QVBoxLayout(updates)
        self.automatic_update_checkbox = QCheckBox(
            "Automatically check for updates"
        )
        self.automatic_update_checkbox.setObjectName("automaticUpdateCheck")
        self.automatic_update_checkbox.setChecked(automatically_check_for_updates)
        updates_layout.addWidget(self.automatic_update_checkbox)
        layout.addWidget(updates)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def selected_theme(self) -> str:
        return self.theme_combo.currentData()

    @property
    def automatically_check_for_updates(self) -> bool:
        return self.automatic_update_checkbox.isChecked()
