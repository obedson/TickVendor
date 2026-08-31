"""Achievement rule evaluator tests."""

import pytest

from src.services.achievement import evaluate_condition


def test_and_or_comparison_rule_evaluation():
    rule = {"operator": "AND", "conditions": [
        {"operator": ">=", "metric": "attendance_count", "value": 5},
        {"operator": "OR", "conditions": [
            {"operator": ">=", "metric": "task_count", "value": 2},
            {"operator": ">=", "metric": "impact_points", "value": 100},
        ]},
    ]}
    assert evaluate_condition(rule, {"attendance_count": 5, "task_count": 0, "impact_points": 100})
    assert not evaluate_condition(rule, {"attendance_count": 4, "task_count": 5, "impact_points": 200})
    with pytest.raises(ValueError):
        evaluate_condition({"operator": "EXEC"}, {})
