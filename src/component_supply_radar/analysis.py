"""Repository-backed historical signal refresh and report projection."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import cast

import duckdb

from component_supply_radar.models import AlertState, DataStatus, PanelRole
from component_supply_radar.reporting import ReportRow
from component_supply_radar.signals import (
    MetricPoint,
    PartScore,
    aggregate_category,
    calculate_part_pressure,
    determine_alert_state,
)
from component_supply_radar.storage import RadarRepository

type MetricRow = tuple[
    str,
    str,
    datetime,
    str,
    str,
    str,
    int | None,
    int | None,
    Decimal | None,
]


def _connect(repository: RadarRepository) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(str(repository.database_path))
    connection.execute("SET TimeZone = 'UTC'")
    return connection


def refresh_category_signals(repository: RadarRepository, *, min_valid_core: int = 1) -> int:
    """Calculate latest 30-day part pressure and persist category results."""
    repository.initialize()
    with _connect(repository) as connection:
        rows = cast(
            list[MetricRow],
            connection.execute(
                """
            SELECT o.source_id, o.mpn, o.observed_at_utc, o.supplier_category,
                   o.canonical_category, o.panel_role, o.quantity_available,
                   o.lead_time_days, MIN(p.unit_price) AS price
            FROM observations o
            LEFT JOIN price_breaks p USING (observation_id)
            GROUP BY ALL
            ORDER BY o.mpn, o.observed_at_utc
            """
            ).fetchall(),
        )
        by_part: dict[str, list[MetricRow]] = defaultdict(list)
        for row in rows:
            by_part[str(row[1])].append(row)
        part_scores: dict[str, list[PartScore]] = defaultdict(list)
        latest_meta: dict[str, tuple[datetime, str, set[str]]] = {}
        configured: dict[str, set[str]] = defaultdict(set)
        for mpn, history in by_part.items():
            latest = history[-1]
            category = str(latest[4])
            role = PanelRole(str(latest[5]))
            if role is PanelRole.CORE:
                configured[category].add(mpn)
            cutoff = latest[2] - timedelta(days=30)
            prior = next((item for item in reversed(history[:-1]) if item[2] <= cutoff), None)
            current_point = MetricPoint(
                None if latest[6] is None else int(latest[6]),
                latest[8],
                None if latest[7] is None else int(latest[7]),
            )
            prior_point = None
            if prior is not None:
                prior_point = MetricPoint(
                    None if prior[6] is None else int(prior[6]),
                    prior[8],
                    None if prior[7] is None else int(prior[7]),
                )
            signal = calculate_part_pressure(
                current_point,
                prior_point,
                stockout_ratio=1.0 if current_point.stock == 0 else 0.0,
            )
            part_scores[category].append(
                PartScore(mpn, category, role, signal.score, str(latest[0]))
            )
            meta = latest_meta.setdefault(category, (latest[2], str(latest[3]), set()))
            meta[2].add(str(latest[0]))

        updated = 0
        for category, scores in part_scores.items():
            if not configured[category]:
                continue
            category_signal = aggregate_category(
                scores,
                configured_core_count=len(configured[category]),
                min_valid_core=min_valid_core,
            )
            observed_at, supplier_category, sources = latest_meta[category]
            calculated_for = observed_at.date()
            history_rows = connection.execute(
                """
                SELECT calculated_for, intensity
                FROM category_signals
                WHERE canonical_category = ? AND calculated_for >= ? AND intensity IS NOT NULL
                ORDER BY calculated_for
                """,
                [category, calculated_for - timedelta(days=6)],
            ).fetchall()
            recent = [(row[0], float(row[1])) for row in history_rows]
            if category_signal.intensity is not None:
                recent.append((calculated_for, category_signal.intensity))
            previous_row = connection.execute(
                """
                SELECT alert_state FROM category_signals
                WHERE canonical_category = ? ORDER BY calculated_for DESC LIMIT 1
                """,
                [category],
            ).fetchone()
            previous = (
                AlertState.NORMAL if previous_row is None else AlertState(str(previous_row[0]))
            )
            alert_state = determine_alert_state(category_signal, recent, previous)
            attribution = "; ".join(
                "Future Electronics" if source == "future" else source for source in sorted(sources)
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO category_signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    category,
                    calculated_for,
                    observed_at,
                    attribution,
                    supplier_category,
                    category_signal.intensity,
                    category_signal.breadth,
                    category_signal.valid_core_count,
                    category_signal.configured_core_count,
                    category_signal.source_count,
                    category_signal.data_status.value,
                    alert_state.value,
                ],
            )
            updated += 1
        return updated


def latest_report_rows(repository: RadarRepository) -> tuple[ReportRow, ...]:
    """Project the latest category signal rows into the report contract."""
    repository.initialize()
    with _connect(repository) as connection:
        rows = connection.execute(
            """
            SELECT * EXCLUDE (calculated_for)
            FROM category_signals
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY canonical_category ORDER BY calculated_for DESC
            ) = 1
            ORDER BY canonical_category
            """
        ).fetchall()
    return tuple(
        ReportRow(
            observed_at_utc=row[1],
            source_attribution=str(row[2]),
            supplier_category=str(row[3]),
            canonical_category=str(row[0]),
            intensity=None if row[4] is None else float(row[4]),
            breadth=None if row[5] is None else float(row[5]),
            alert_state=AlertState(str(row[10])),
            valid_core_count=int(row[6]),
            configured_core_count=int(row[7]),
            source_count=int(row[8]),
            data_status=DataStatus(str(row[9])),
            direct_provenance=(),
            thematic_provenance=(),
        )
        for row in rows
    )
