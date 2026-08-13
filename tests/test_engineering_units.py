import pytest
from PySide6.QtWidgets import QApplication, QInputDialog

from serialscope.data import ENGINEERING_UNITS, is_builtin_unit
from serialscope.ui.unit_selector import UnitSelector


def test_required_catalogue_categories_and_units_exist() -> None:
    assert ENGINEERING_UNITS["Temperature"] == ("°C", "°F", "K")
    assert all(
        unit in ENGINEERING_UNITS["Pressure"]
        for unit in ("bar", "kPa", "psi", "atm")
    )
    assert "Volumetric Flow" in ENGINEERING_UNITS
    assert "Mass Flow" in ENGINEERING_UNITS
    assert "kg/h" in ENGINEERING_UNITS["Mass Flow"]
    assert "rpm" in ENGINEERING_UNITS["Rotation / Frequency"]
    assert "mA" in ENGINEERING_UNITS["Electrical"]
    assert "%" in ENGINEERING_UNITS["Concentration / Fraction"]


@pytest.mark.parametrize("unit", ["°C", "K", "bar", "kPa", "psi", "atm", "kg/h", "rpm", "mA", "%"])
def test_builtin_unit_selection_stores_actual_string(unit: str) -> None:
    application = QApplication.instance() or QApplication([])
    selector = UnitSelector()
    selector._actions_by_unit[unit].trigger()
    assert selector.unit == unit
    assert selector.text() == unit
    assert is_builtin_unit(selector.unit)
    selector.close()
    application.processEvents()


def test_category_submenus_and_current_check_are_available() -> None:
    application = QApplication.instance() or QApplication([])
    selector = UnitSelector("bar")
    assert selector.category_menu("Temperature") is not None
    assert selector.category_menu("Pressure") is not None
    assert selector.category_menu("Volumetric Flow") is not None
    assert selector.category_menu("Mass Flow") is not None
    assert selector._actions_by_unit["bar"].isChecked()
    selector.close()
    application.processEvents()


def test_custom_unicode_unit_and_no_unit(monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    selector = UnitSelector("legacy-unit")
    assert selector.unit == "legacy-unit"
    assert selector.is_custom

    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: (" Nm³/h ", True))
    selector._choose_custom_unit()
    assert selector.unit == "Nm³/h"
    assert selector.is_custom

    other = selector.category_menu("Other")
    assert other is not None
    next(action for action in other.actions() if action.text() == "No unit").trigger()
    assert selector.unit == ""
    assert selector.text() == "No unit"
    selector.close()
    application.processEvents()
