"""Compact application preferences dialog."""

from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from serialscope.ui.fonts import (
    NumericDisplayStyle,
    normalize_numeric_display_style,
    numeric_display_style_items,
)
from serialscope.settings import (
    DASHBOARD_TREND_WINDOW_OPTIONS,
    DEFAULT_DASHBOARD_TREND_WINDOW_SECONDS,
    normalize_dashboard_trend_window,
)


TREND_WINDOW_LABELS = {
    30: "30 seconds",
    60: "1 minute",
    300: "5 minutes",
    600: "10 minutes",
    1_800: "30 minutes",
    3_600: "1 hour",
}


class PreferencesDialog(QDialog):
    """Edit preferences that benefit from explicit confirmation."""

    def __init__(
        self,
        current_theme: str,
        parent: QWidget | None = None,
        automatically_check_for_updates: bool = True,
        dashboard_numeric_style: str = NumericDisplayStyle.DEFAULT.value,
        dashboard_trend_window_seconds: int = DEFAULT_DASHBOARD_TREND_WINDOW_SECONDS,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("preferencesDialog")
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
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

        dashboard = QGroupBox("Dashboard")
        dashboard_form = QFormLayout(dashboard)
        dashboard_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.numeric_style_combo = QComboBox()
        self.numeric_style_combo.setObjectName("dashboardNumericStyleCombo")
        for label, identifier in numeric_display_style_items():
            self.numeric_style_combo.addItem(label, identifier)
        selected = normalize_numeric_display_style(dashboard_numeric_style).value
        self.numeric_style_combo.setCurrentIndex(
            max(0, self.numeric_style_combo.findData(selected))
        )
        numeric_style_label = QLabel("Numeric style")
        numeric_style_label.setObjectName("dashboardNumericStyleLabel")
        dashboard_form.addRow(numeric_style_label, self.numeric_style_combo)
        self.trend_window_combo = QComboBox()
        self.trend_window_combo.setObjectName("dashboardTrendWindowCombo")
        for seconds in DASHBOARD_TREND_WINDOW_OPTIONS:
            self.trend_window_combo.addItem(TREND_WINDOW_LABELS[seconds], seconds)
        selected_window = normalize_dashboard_trend_window(
            dashboard_trend_window_seconds
        )
        self.trend_window_combo.setCurrentIndex(
            max(0, self.trend_window_combo.findData(selected_window))
        )
        trend_window_label = QLabel("Trend window")
        trend_window_label.setObjectName("dashboardTrendWindowLabel")
        dashboard_form.addRow(trend_window_label, self.trend_window_combo)
        layout.addWidget(dashboard)

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
    def dashboard_numeric_style(self) -> str:
        return self.numeric_style_combo.currentData()

    @property
    def dashboard_trend_window_seconds(self) -> int:
        return int(self.trend_window_combo.currentData())

    @property
    def automatically_check_for_updates(self) -> bool:
        return self.automatic_update_checkbox.isChecked()
