"""Categorized engineering-unit selector with unrestricted custom values."""

from PySide6.QtWidgets import QInputDialog, QMenu, QToolButton, QWidget

from serialscope.data.engineering_units import ENGINEERING_UNITS, is_builtin_unit


class UnitSelector(QToolButton):
    def __init__(self, unit: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("engineeringUnitSelector")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._unit = unit.strip()
        self._actions_by_unit = {}
        self._category_menus: dict[str, QMenu] = {}
        self._menu = QMenu(self)
        self._menu.setObjectName("engineeringUnitMenu")
        for category, units in ENGINEERING_UNITS.items():
            submenu = self._menu.addMenu(category)
            self._category_menus[category] = submenu
            submenu.setObjectName("engineeringUnitCategory")
            for value in units:
                action = submenu.addAction(value)
                action.setCheckable(True)
                action.triggered.connect(
                    lambda _checked=False, selected=value: self.set_unit(selected)
                )
                self._actions_by_unit[value] = action
        other = self._menu.addMenu("Other")
        self._category_menus["Other"] = other
        custom_action = other.addAction("Custom...")
        custom_action.triggered.connect(self._choose_custom_unit)
        no_unit_action = other.addAction("No unit")
        no_unit_action.triggered.connect(lambda: self.set_unit(""))
        self.setMenu(self._menu)
        self._refresh_presentation()

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def is_custom(self) -> bool:
        return bool(self._unit) and not is_builtin_unit(self._unit)

    def set_unit(self, unit: str) -> None:
        self._unit = unit.strip()
        self._refresh_presentation()

    def category_menu(self, category: str) -> QMenu | None:
        return self._category_menus.get(category)

    def _choose_custom_unit(self) -> None:
        value, accepted = QInputDialog.getText(
            self,
            "Custom engineering unit",
            "Unit",
            text=self._unit,
        )
        if accepted:
            self.set_unit(value)

    def _refresh_presentation(self) -> None:
        self.setText(self._unit or "No unit")
        self.setToolTip(
            f"Custom unit: {self._unit}" if self.is_custom else "Select engineering unit"
        )
        for value, action in self._actions_by_unit.items():
            action.setChecked(value == self._unit)
