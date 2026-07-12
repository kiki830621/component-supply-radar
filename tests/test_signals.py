from datetime import date, timedelta
from decimal import Decimal

import pytest

from component_supply_radar.models import AlertState, DataStatus, PanelRole
from component_supply_radar.signals import (
    CategorySignal,
    MetricPoint,
    PartScore,
    aggregate_category,
    calculate_part_pressure,
    determine_alert_state,
)


def test_maximum_component_scores_are_capped_at_100() -> None:
    signal = calculate_part_pressure(
        current=MetricPoint(stock=0, price=Decimal("1.20"), lead_days=112),
        thirty_day=MetricPoint(stock=100, price=Decimal("1.00"), lead_days=56),
        stockout_ratio=1.0,
    )

    assert signal.score == 100
    assert signal.data_status is DataStatus.SUFFICIENT


def test_missing_comparison_is_not_zero_pressure() -> None:
    signal = calculate_part_pressure(
        MetricPoint(10, Decimal("1"), 14), thirty_day=None, stockout_ratio=0
    )

    assert signal.score is None
    assert signal.data_status is DataStatus.INSUFFICIENT


def test_category_uses_core_median_and_excludes_exploratory() -> None:
    scores = [
        PartScore(str(value), "power", PanelRole.CORE, float(value), "future")
        for value in (10, 20, 30, 40, 100)
    ]
    scores.append(PartScore("explore", "power", PanelRole.EXPLORATORY, 100, "future"))

    category = aggregate_category(scores, configured_core_count=5, min_valid_core=3)

    assert category.intensity == 30
    assert category.valid_core_count == 5
    assert category.configured_core_count == 5
    assert category.breadth == pytest.approx(1 / 5)


def test_category_below_minimum_coverage_is_unknown() -> None:
    category = aggregate_category(
        [PartScore("A", "power", PanelRole.CORE, 80, "future")],
        configured_core_count=5,
        min_valid_core=3,
    )

    assert category.data_status is DataStatus.INSUFFICIENT
    assert category.alert_state is AlertState.UNKNOWN


@pytest.mark.parametrize(
    ("intensity", "history", "previous", "expected"),
    [
        (65, [65], AlertState.NORMAL, AlertState.WATCH),
        (75, [65, 62, 75], AlertState.WATCH, AlertState.CONFIRMED),
        (50, [50], AlertState.CONFIRMED, AlertState.RECOVERING),
        (30, [30], AlertState.RECOVERING, AlertState.NORMAL),
    ],
)
def test_alert_state_transitions(
    intensity: float,
    history: list[float],
    previous: AlertState,
    expected: AlertState,
) -> None:
    today = date(2026, 7, 11)
    category = CategorySignal(
        "power", intensity, 0.5, 5, 5, 1, DataStatus.SUFFICIENT, AlertState.NORMAL
    )
    recent = [(today - timedelta(days=index), value) for index, value in enumerate(history)]

    assert determine_alert_state(category, recent, previous) is expected


def test_failed_collection_after_confirmed_is_unknown() -> None:
    category = CategorySignal(
        "power", None, None, 0, 5, 0, DataStatus.INSUFFICIENT, AlertState.UNKNOWN
    )

    assert determine_alert_state(category, [], AlertState.CONFIRMED) is AlertState.UNKNOWN
