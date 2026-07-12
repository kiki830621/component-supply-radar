"""Escaped HTML and UTF-8 CSV research reports."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader

from component_supply_radar.exposure import RESEARCH_NOTICE
from component_supply_radar.models import AlertState, DataStatus


@dataclass(frozen=True, slots=True)
class ReportRow:
    observed_at_utc: datetime
    source_attribution: str
    supplier_category: str
    canonical_category: str
    intensity: float | None
    breadth: float | None
    alert_state: AlertState
    valid_core_count: int
    configured_core_count: int
    source_count: int
    data_status: DataStatus
    direct_provenance: tuple[str, ...]
    thematic_provenance: tuple[str, ...]


def _display_number(value: float | None, status: DataStatus) -> str:
    if status is DataStatus.INSUFFICIENT or value is None:
        return "資料不足"
    return f"{value:.2f}"


def _render_rows(rows: tuple[ReportRow, ...], timezone: str) -> list[dict[str, str | int]]:
    zone = ZoneInfo(timezone)
    rendered: list[dict[str, str | int]] = []
    for row in rows:
        rendered.append(
            {
                "observed_at": row.observed_at_utc.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S"),
                "source": row.source_attribution,
                "supplier_category": row.supplier_category,
                "canonical_category": row.canonical_category,
                "intensity": _display_number(row.intensity, row.data_status),
                "breadth": _display_number(row.breadth, row.data_status),
                "alert_state": row.alert_state.value,
                "valid_core_count": row.valid_core_count,
                "configured_core_count": row.configured_core_count,
                "source_count": row.source_count,
                "data_status": row.data_status.value,
                "direct_provenance": "; ".join(row.direct_provenance),
                "thematic_provenance": "; ".join(row.thematic_provenance),
            }
        )
    return rendered


def write_report(rows: tuple[ReportRow, ...], output_dir: Path, timezone: str) -> tuple[Path, Path]:
    """Write the latest escaped HTML summary and UTF-8-SIG CSV detail."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = _render_rows(rows, timezone)
    environment = Environment(
        loader=PackageLoader("component_supply_radar", "templates"),
        autoescape=True,
    )
    html = environment.get_template("report.html.j2").render(rows=rendered, notice=RESEARCH_NOTICE)
    html_path = output_dir / "latest.html"
    html_path.write_text(html, encoding="utf-8")

    csv_path = output_dir / "latest.csv"
    fieldnames = (
        list(rendered[0])
        if rendered
        else [
            "observed_at",
            "source",
            "supplier_category",
            "canonical_category",
            "intensity",
            "breadth",
            "alert_state",
            "valid_core_count",
            "configured_core_count",
            "source_count",
            "data_status",
            "direct_provenance",
            "thematic_provenance",
        ]
    )
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rendered)
    return html_path, csv_path
