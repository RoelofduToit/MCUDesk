import math

import pytest

from serialscope.data import (
    ExpressionError,
    evaluate_expression,
    expression_names,
)


def test_expression_evaluates_arithmetic_and_functions() -> None:
    assert evaluate_expression("1 + 2 * 3", {}) == 7
    assert evaluate_expression("(TC1 - TC2) / 2", {"TC1": 10, "TC2": 4}) == 3
    assert evaluate_expression("abs(-3) + sqrt(16)", {}) == 7
    assert evaluate_expression("min(5, 2, 9)", {}) == 2
    assert evaluate_expression("pow(2, 3)", {}) == 8
    assert evaluate_expression("sin(0) + cos(0)", {}) == pytest.approx(1.0)


def test_expression_names_ignore_functions() -> None:
    assert expression_names("abs(TC1 - TC2) / Flow") == ("TC1", "TC2", "Flow")


def test_expression_rejects_unsafe_constructs() -> None:
    with pytest.raises(ExpressionError):
        evaluate_expression("__import__('os').system('x')", {})
    with pytest.raises(ExpressionError):
        evaluate_expression("TC1.real", {"TC1": 1})
    with pytest.raises(ExpressionError):
        evaluate_expression("[1, 2]", {})
    with pytest.raises(ExpressionError):
        evaluate_expression("lambda: 1", {})


def test_expression_reports_missing_values_and_division_by_zero() -> None:
    with pytest.raises(ExpressionError, match="Unknown channel"):
        evaluate_expression("A + 1", {})
    with pytest.raises(ExpressionError, match="Division by zero"):
        evaluate_expression("1 / 0", {})
    with pytest.raises(ExpressionError, match="Invalid arguments"):
        evaluate_expression("log(-1)", {})
    assert math.isnan(float("nan"))
