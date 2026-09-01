"""Safe, extensible achievement condition-tree evaluator."""

from collections.abc import Callable, Sequence
from typing import Any

SUPPORTED_COMPARISONS = {">=", "<=", "="}
SUPPORTED_AGGREGATES = {"Count", "Sum", "Streak", "Unique event count"}
CUSTOM_AGGREGATES: dict[str, Callable[[Sequence[Any]], int | float]] = {}


def register_aggregate(
    name: str, handler: Callable[[Sequence[Any]], int | float]
) -> None:
    if not name or name in SUPPORTED_COMPARISONS | SUPPORTED_AGGREGATES:
        raise ValueError("Aggregate name must be new and non-empty")
    CUSTOM_AGGREGATES[name] = handler


def compare(actual: float, expected: float, operator: str) -> bool:
    if operator == ">=":
        return actual >= expected
    if operator == "<=":
        return actual <= expected
    if operator == "=":
        return actual == expected
    raise ValueError(f"Unsupported comparison operator: {operator}")


def longest_truthy_streak(values: Sequence[Any]) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if bool(value) else 0
        longest = max(longest, current)
    return longest


def aggregate(operator: str, values: Any) -> int | float:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise TypeError(f"{operator} requires a sequence metric")
    if operator == "Count":
        return len(values)
    if operator == "Sum":
        return sum(values)
    if operator == "Streak":
        return longest_truthy_streak(values)
    if operator == "Unique event count":
        return len(set(values))
    if operator in CUSTOM_AGGREGATES:
        return CUSTOM_AGGREGATES[operator](values)
    raise ValueError(f"Unsupported aggregate operator: {operator}")


def evaluate_condition(node: dict[str, Any], metrics: dict[str, Any]) -> bool:
    operator = node.get("operator")
    if operator == "AND":
        conditions = node.get("conditions", [])
        return bool(conditions) and all(evaluate_condition(child, metrics) for child in conditions)
    if operator == "OR":
        conditions = node.get("conditions", [])
        return bool(conditions) and any(evaluate_condition(child, metrics) for child in conditions)
    if operator not in SUPPORTED_COMPARISONS | SUPPORTED_AGGREGATES | CUSTOM_AGGREGATES.keys():
        raise ValueError(f"Unsupported achievement operator: {operator}")
    metric = node.get("metric")
    if metric not in metrics:
        return False
    expected = node.get("value", 0)
    if operator in SUPPORTED_COMPARISONS:
        return compare(metrics[metric], expected, operator)
    if operator in SUPPORTED_AGGREGATES | CUSTOM_AGGREGATES.keys():
        return compare(
            aggregate(operator, metrics[metric]),
            expected,
            str(node.get("comparison", ">=")),
        )
    raise ValueError(f"Unsupported achievement operator: {operator}")
