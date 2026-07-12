from datetime import UTC, datetime

from component_supply_radar.exposure import RESEARCH_NOTICE, ExposureRegistry, attach_exposures
from component_supply_radar.models import (
    AlertState,
    DataStatus,
    DirectExposure,
    ThematicExposure,
)
from component_supply_radar.signals import CategorySignal

REVIEWED_AT = datetime(2026, 7, 11, tzinfo=UTC)


def test_direct_and_thematic_exposures_keep_provenance_separate() -> None:
    direct = DirectExposure(
        "onsemi",
        "ON",
        "2026-Q3",
        "analyst@example.com",
        REVIEWED_AT,
        "https://www.onsemi.com/company/about-onsemi",
    )
    thematic = ThematicExposure(
        "memory",
        "2330.TW",
        "downstream",
        "2026-Q3",
        "analyst@example.com",
        REVIEWED_AT,
        "internal-research-note-1",
    )
    registry = ExposureRegistry((direct,), (thematic,))

    assert registry.direct_for_manufacturer("onsemi") == (direct,)
    assert registry.direct_for_manufacturer("unknown") == ()
    assert registry.thematic_for_category("memory") == (thematic,)


def test_attaching_thematic_exposure_does_not_change_pressure_score() -> None:
    signal = CategorySignal("memory", 75, 0.5, 5, 5, 1, DataStatus.SUFFICIENT, AlertState.CONFIRMED)
    thematic = ThematicExposure(
        "memory",
        "2330.TW",
        "downstream",
        "2026-Q3",
        "analyst@example.com",
        REVIEWED_AT,
        "internal-research-note-1",
    )

    context = attach_exposures(signal, ExposureRegistry((), (thematic,)), ["unknown"])

    assert context.signal is signal
    assert context.signal.intensity == 75
    assert context.direct == ()
    assert context.thematic == (thematic,)
    assert context.thematic_is_research_assumption is True


def test_research_notice_contains_no_trade_instruction() -> None:
    lowered = RESEARCH_NOTICE.lower()
    assert "buy" not in lowered
    assert "sell" not in lowered
    assert "position size" not in lowered
    assert "return prediction" not in lowered
