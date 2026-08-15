"""Restricted arithmetic expressions for calculated channels."""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Mapping


class ExpressionError(ValueError):
    """A user-presentable expression problem."""


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
ALLOWED_FUNCTIONS = {
    "abs": abs,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "floor": math.floor,
    "ceil": math.ceil,
    "pow": pow,
}


def expression_names(expression: str) -> tuple[str, ...]:
    """Return identifier names referenced by a validated expression."""
    tree = parse_expression(expression)
    names: list[str] = []

    class Collector(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
            if node.id not in ALLOWED_FUNCTIONS and node.id not in names:
                names.append(node.id)

    Collector().visit(tree)
    return tuple(names)


def parse_expression(expression: str) -> ast.Expression:
    """Parse and reject empty or syntactically invalid expressions."""
    text = expression.strip()
    if not text:
        raise ExpressionError("Enter an expression.")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as error:
        raise ExpressionError(f"Invalid expression: {error.msg}.") from error
    _assert_supported(tree)
    return tree


def evaluate_expression(
    expression: str, variables: Mapping[str, int | float]
) -> float:
    """Evaluate a restricted expression against numeric channel variables."""
    tree = parse_expression(expression)
    value = _eval_node(tree.body, variables)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExpressionError("The expression did not produce a number.")
    if not math.isfinite(float(value)):
        raise ExpressionError("The expression did not produce a finite number.")
    return value


def _assert_supported(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.Expression,
                ast.Load,
                ast.BinOp,
                ast.UnaryOp,
                ast.Call,
                ast.Name,
                ast.Constant,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.Pow,
                ast.Mod,
                ast.UAdd,
                ast.USub,
            ),
        ):
            continue
        raise ExpressionError("This expression uses an unsupported construct.")


def _eval_node(node: ast.AST, variables: Mapping[str, int | float]) -> int | float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExpressionError("Only numeric literals are allowed.")
        if not math.isfinite(float(node.value)):
            raise ExpressionError("Numeric literals must be finite.")
        return node.value
    if isinstance(node, ast.Name):
        if node.id in ALLOWED_FUNCTIONS:
            raise ExpressionError(f"{node.id} must be called as a function.")
        try:
            value = variables[node.id]
        except KeyError as error:
            raise ExpressionError(f"Unknown channel: {node.id}.") from error
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ExpressionError(f"{node.id} is not a valid number.")
        if not math.isfinite(float(value)):
            raise ExpressionError(f"{node.id} is not a valid number.")
        return value
    if isinstance(node, ast.BinOp):
        operation = _BINOPS.get(type(node.op))
        if operation is None:
            raise ExpressionError("This operator is not allowed.")
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        try:
            return operation(left, right)
        except ZeroDivisionError as error:
            raise ExpressionError("Division by zero.") from error
        except OverflowError as error:
            raise ExpressionError("The result is too large.") from error
    if isinstance(node, ast.UnaryOp):
        operation = _UNARY.get(type(node.op))
        if operation is None:
            raise ExpressionError("This operator is not allowed.")
        return operation(_eval_node(node.operand, variables))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
            raise ExpressionError("This function is not allowed.")
        if node.keywords:
            raise ExpressionError("Keyword arguments are not allowed.")
        function = ALLOWED_FUNCTIONS[node.func.id]
        arguments = [_eval_node(argument, variables) for argument in node.args]
        try:
            result = function(*arguments)
        except (TypeError, ValueError) as error:
            raise ExpressionError(
                f"Invalid arguments for {node.func.id}()."
            ) from error
        except OverflowError as error:
            raise ExpressionError("The result is too large.") from error
        return result
    raise ExpressionError("This expression uses an unsupported construct.")
