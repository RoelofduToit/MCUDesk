"""Built-in engineering-unit catalogue for presentation and future extension."""

from types import MappingProxyType


_UNITS = {
    "Temperature": ("°C", "°F", "K"),
    "Pressure": ("Pa", "kPa", "MPa", "bar", "mbar", "psi", "atm", "mmHg"),
    "Volumetric Flow": ("m³/s", "m³/h", "L/s", "L/min", "L/h", "mL/min"),
    "Mass Flow": ("kg/s", "kg/h", "g/s", "g/min"),
    "Mass": ("mg", "g", "kg", "t"),
    "Rotation / Frequency": ("rpm", "Hz", "rad/s"),
    "Electrical": ("V", "mV", "kV", "A", "mA", "µA", "W", "kW", "MW", "Ω", "kΩ"),
    "Length": ("mm", "cm", "m", "km", "in", "ft"),
    "Velocity": ("m/s", "km/h", "ft/s"),
    "Time": ("ms", "s", "min", "h"),
    "Concentration / Fraction": ("%", "ppm", "ppb"),
    "Energy": ("J", "kJ", "MJ", "Wh", "kWh"),
}

ENGINEERING_UNITS = MappingProxyType(_UNITS)


def is_builtin_unit(unit: str) -> bool:
    return any(unit in units for units in ENGINEERING_UNITS.values())
