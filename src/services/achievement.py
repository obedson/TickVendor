"""Safe, extensible achievement condition-tree evaluator."""

from typing import Any

SUPPORTED_COMPARISONS = {">=", "<=", "="}


def evaluate_condition(node: dict[str, Any], metrics: dict[str, int | float]) -> bool:
    operator = node.get("operator")
    if operator == "AND":
        return all(evaluate_condition(child, metrics) for child in node.get("conditions", []))
    if operator == "OR":
        return any(evaluate_condition(child, metrics) for child in node.get("conditions", []))
    if operator in SUPPORTED_COMPARISONS:
        metric = node.get("metric")
        if metric not in metrics:
            return False
        actual, expected = metrics[metric], node.get("value", 0)
        if operator == ">=": return actual >= expected
        if operator == "<=": return actual <= expected
        return actual == expected
    raise ValueError(f"Unsupported achievement operator: {operator}")
