"""Transparent part and category supply-pressure calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from component_supply_radar.models import AlertState, DataStatus, PanelRole


@dataclass(frozen=True, slots=True)
class MetricPoint:
    stock: int | None
    price: Decimal | None
    lead_days: int | None


@dataclass(frozen=True, slots=True)
class PartSignal:
    score: float | None
    inventory_component: float | None
    lead_component: float | None
    price_component: float | None
    breadth_component: float | None
    data_status: DataStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PartScore:
    mpn: str
    canonical_category: str
    panel_role: PanelRole
    score: float | None
    source_id: str


@dataclass(frozen=True, slots=True)
class CategorySignal:
    canonical_category: str
    intensity: float | None
    breadth: float | None
    valid_core_count: int
    configured_core_count: int
    source_count: int
    data_status: DataStatus
    alert_state: AlertState


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def calculate_part_pressure(
    current: MetricPoint,
    thirty_day: MetricPoint | None,
    stockout_ratio: float,
) -> PartSignal:
    """Calculate four bounded, explainable pressure components."""
    if thirty_day is None:
        return PartSignal(None, None, None, None, None, DataStatus.INSUFFICIENT, ())
    components: list[float] = []
    reasons: list[str] = []
    inventory_component: float | None = None
    if current.stock is not None and thirty_day.stock is not None and thirty_day.stock > 0:
        inventory_change = (current.stock - thirty_day.stock) / thirty_day.stock
        inventory_component = _clamp(-inventory_change / 0.50) * 35
        components.append(inventory_component)
        if inventory_component > 0:
            reasons.append("inventory-decline")
    lead_component: float | None = None
    if current.lead_days is not None and thirty_day.lead_days is not None:
        lead_component = _clamp((current.lead_days - thirty_day.lead_days) / 56) * 25
        components.append(lead_component)
        if lead_component > 0:
            reasons.append("lead-time-increase")
    price_component: float | None = None
    if current.price is not None and thirty_day.price is not None and thirty_day.price > 0:
        price_change = float((current.price - thirty_day.price) / thirty_day.price)
        price_component = _clamp(price_change / 0.20) * 25
        components.append(price_component)
        if price_component > 0:
            reasons.append("price-increase")
    breadth_component = _clamp(stockout_ratio) * 15
    components.append(breadth_component)
    if breadth_component > 0:
        reasons.append("stockout-breadth")
    if len(components) == 1:
        return PartSignal(None, None, None, None, None, DataStatus.INSUFFICIENT, ())
    return PartSignal(
        score=round(sum(components), 6),
        inventory_component=inventory_component,
        lead_component=lead_component,
        price_component=price_component,
        breadth_component=breadth_component,
        data_status=DataStatus.SUFFICIENT,
        reasons=tuple(reasons),
    )


def aggregate_category(
    scores: list[PartScore],
    *,
    configured_core_count: int,
    min_valid_core: int,
    pressure_threshold: float = 60,
) -> CategorySignal:
    """Aggregate only valid core scores using median intensity and pressure breadth."""
    if configured_core_count < 0 or min_valid_core < 1:
        raise ValueError("coverage counts are invalid")
    core = [
        score for score in scores if score.panel_role is PanelRole.CORE and score.score is not None
    ]
    category = scores[0].canonical_category if scores else "unknown"
    if len(core) < min_valid_core:
        return CategorySignal(
            category,
            None,
            None,
            len(core),
            configured_core_count,
            len({score.source_id for score in core}),
            DataStatus.INSUFFICIENT,
            AlertState.UNKNOWN,
        )
    values = [float(score.score) for score in core if score.score is not None]
    return CategorySignal(
        category,
        float(median(values)),
        sum(value >= pressure_threshold for value in values) / len(values),
        len(core),
        configured_core_count,
        len({score.source_id for score in core}),
        DataStatus.SUFFICIENT,
        AlertState.NORMAL,
    )


def determine_alert_state(
    current: CategorySignal,
    recent_intensities: list[tuple[date, float]],
    previous: AlertState,
) -> AlertState:
    """Apply the documented seven-day multi-stage alert state machine."""
    if current.data_status is DataStatus.INSUFFICIENT or current.intensity is None:
        return AlertState.UNKNOWN
    latest = current.intensity
    if recent_intensities:
        newest_date = max(day for day, _ in recent_intensities)
        window_start = newest_date - timedelta(days=6)
        qualifying = sum(
            value >= 60 for day, value in recent_intensities if window_start <= day <= newest_date
        )
    else:
        qualifying = 0
    if latest >= 70 and qualifying >= 3:
        return AlertState.CONFIRMED
    if latest >= 60:
        return AlertState.WATCH
    if previous in {AlertState.CONFIRMED, AlertState.RECOVERING} and latest >= 40:
        return AlertState.RECOVERING
    return AlertState.NORMAL
