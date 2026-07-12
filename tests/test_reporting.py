from datetime import UTC, datetime
from pathlib import Path

from component_supply_radar.models import AlertState, DataStatus
from component_supply_radar.reporting import ReportRow, write_report


def test_report_escapes_html_and_labels_insufficient_data(tmp_path: Path) -> None:
    row = ReportRow(
        observed_at_utc=datetime(2026, 7, 11, 0, 0, tzinfo=UTC),
        source_attribution="Future Electronics",
        supplier_category="<script>alert(1)</script>",
        canonical_category="power-semiconductor",
        intensity=None,
        breadth=None,
        alert_state=AlertState.UNKNOWN,
        valid_core_count=1,
        configured_core_count=5,
        source_count=1,
        data_status=DataStatus.INSUFFICIENT,
        direct_provenance=("ON | evidence:https://example.com/direct",),
        thematic_provenance=("2330.TW | research-assumption:downstream",),
    )

    html_path, csv_path = write_report((row,), tmp_path, "Asia/Taipei")

    html = html_path.read_text(encoding="utf-8")
    assert "2026-07-11 08:00:00" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "資料不足" in html
    assert "ON | evidence:https://example.com/direct" in html
    assert csv_path.exists()


def test_report_csv_is_utf8_sig_and_does_not_substitute_zero(tmp_path: Path) -> None:
    row = ReportRow(
        datetime(2026, 7, 11, 0, 0, tzinfo=UTC),
        "Future Electronics",
        "Schottky Diodes",
        "power-semiconductor",
        None,
        None,
        AlertState.UNKNOWN,
        1,
        5,
        1,
        DataStatus.INSUFFICIENT,
        (),
        (),
    )

    _, csv_path = write_report((row,), tmp_path, "Asia/Taipei")

    content = csv_path.read_bytes()
    assert content.startswith(b"\xef\xbb\xbf")
    decoded = content.decode("utf-8-sig")
    assert "intensity,breadth" in decoded
    assert ",資料不足,資料不足," in decoded
