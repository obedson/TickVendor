"""Achievement evaluator aggregate-operator tests."""

from src.services.achievement import evaluate_condition


def test_count_sum_streak_and_unique_event_operators():
    metrics = {
        "attendance_events": ["event-a", "event-a", "event-b"],
        "contribution_amounts": [10, 20, 30],
        "weekly_activity": [True, True, True, False],
    }
    assert evaluate_condition(
        {"operator": "Count", "metric": "attendance_events", "comparison": ">=", "value": 3},
        metrics,
    )
    assert evaluate_condition(
        {"operator": "Unique event count", "metric": "attendance_events", "comparison": "=", "value": 2},
        metrics,
    )
    assert evaluate_condition(
        {"operator": "Sum", "metric": "contribution_amounts", "comparison": ">=", "value": 60},
        metrics,
    )
    assert evaluate_condition(
        {"operator": "Streak", "metric": "weekly_activity", "comparison": ">=", "value": 3},
        metrics,
    )
