from datetime import UTC, datetime
from decimal import Decimal

import pytest

from component_supply_radar.models import (
    AlertState,
    DirectExposure,
    Observation,
    PanelMember,
    PanelRole,
    PriceBreak,
    RunResult,
    RunStatus,
    ThematicExposure,
)

NOW = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)


def valid_observation(**changes: object) -> Observation:
    values: dict[str, object] = {
        "source_id": "future",
        "mpn": "BAT54STA",
        "manufacturer": "onsemi",
        "observed_at_utc": datetime(2026, 7, 11, 0, 0, tzinfo=UTC),
        "supplier_category": "Schottky Diodes",
        "canonical_category": "power-semiconductor",
        "taxonomy_version": "2026-v1",
        "panel_version": "2026-Q3",
        "panel_role": PanelRole.CORE,
        "quantity_available": 5000,
        "quantity_factory": 0,
        "quantity_on_order": 30000,
        "minimum_order_quantity": 100,
        "order_multiple": 100,
        "lead_time_days": 70,
        "lifecycle": "ACTIVE",
        "region": "NA",
        "currency": "USD",
        "price_breaks": (PriceBreak(100, 199, Decimal("0.218000"), "USD"),),
        "source_file_hash": None,
        "ingest_hash": "a" * 64,
    }
    values.update(changes)
    return Observation(**values)  # type: ignore[arg-type]


def test_observation_requires_utc_timestamp() -> None:
    with pytest.raises(ValueError, match="UTC"):
        valid_observation(observed_at_utc=datetime(2026, 7, 11, 0, 0))


def test_price_break_requires_decimal_and_iso_currency() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        PriceBreak(1, None, 0.218, "USD")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="currency"):
        PriceBreak(1, None, Decimal("0.218"), "usd")


def test_panel_member_uses_explicit_role_and_both_categories() -> None:
    member = PanelMember(
        mpn="BAT54STA",
        manufacturer="onsemi",
        supplier_category="Schottky Diodes",
        canonical_category="power-semiconductor",
        taxonomy_version="2026-v1",
        panel_version="2026-Q3",
        role=PanelRole.EXPLORATORY,
        active=True,
    )

    assert member.role is PanelRole.EXPLORATORY
    assert member.supplier_category == "Schottky Diodes"
    assert member.canonical_category == "power-semiconductor"
    assert member.taxonomy_version == "2026-v1"


def test_exposure_records_keep_provenance_and_kind_separate() -> None:
    reviewed_at = datetime(2026, 7, 11, 1, 0, tzinfo=UTC)
    direct = DirectExposure(
        manufacturer="onsemi",
        ticker="ON",
        mapping_version="2026-Q3",
        reviewed_by="analyst@example.com",
        reviewed_at_utc=reviewed_at,
        evidence_ref="https://www.onsemi.com/company/about-onsemi",
    )
    thematic = ThematicExposure(
        canonical_category="memory",
        ticker="2330.TW",
        relationship="downstream",
        mapping_version="2026-Q3",
        reviewed_by="analyst@example.com",
        reviewed_at_utc=reviewed_at,
        evidence_ref="internal-research-note-1",
    )

    assert direct.manufacturer == "onsemi"
    assert thematic.relationship == "downstream"


def test_run_result_has_typed_status_and_nonnegative_counts() -> None:
    result = RunResult("future", RunStatus.PARTIAL, NOW, NOW, 2, 1, 1, "one failed")
    assert result.status is RunStatus.PARTIAL
    with pytest.raises(ValueError, match="negative"):
        RunResult("future", RunStatus.FAILED, NOW, NOW, -1, 0, 0, None)


def test_alert_state_values_are_stable() -> None:
    assert [state.value for state in AlertState] == [
        "normal",
        "watch",
        "confirmed",
        "recovering",
        "unknown",
    ]
