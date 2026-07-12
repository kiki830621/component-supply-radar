"""Versioned DuckDB schema and transactional repository."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import duckdb

from component_supply_radar.models import Observation, RunResult, RunStatus
from component_supply_radar.policy import SourcePolicy, require_persistence

SCHEMA_VERSION = 1
COUNTABLE_TABLES = {
    "schema_migrations",
    "source_policies",
    "observations",
    "price_breaks",
    "collection_runs",
    "category_signals",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at_utc TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS source_policies (
    source_id VARCHAR PRIMARY KEY,
    persist_allowed BOOLEAN NOT NULL,
    cloud_share_allowed BOOLEAN NOT NULL,
    raw_retention_days INTEGER NOT NULL CHECK (raw_retention_days >= 0),
    attribution_required BOOLEAN NOT NULL,
    terms_reviewed_at DATE NOT NULL,
    terms_url VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    observation_id UUID PRIMARY KEY,
    source_id VARCHAR NOT NULL,
    mpn VARCHAR NOT NULL,
    manufacturer VARCHAR NOT NULL,
    observed_at_utc TIMESTAMPTZ NOT NULL,
    supplier_category VARCHAR NOT NULL,
    canonical_category VARCHAR NOT NULL,
    taxonomy_version VARCHAR NOT NULL,
    panel_version VARCHAR NOT NULL,
    panel_role VARCHAR NOT NULL CHECK (panel_role IN ('core', 'exploratory')),
    quantity_available BIGINT CHECK (quantity_available >= 0),
    quantity_factory BIGINT CHECK (quantity_factory >= 0),
    quantity_on_order BIGINT CHECK (quantity_on_order >= 0),
    minimum_order_quantity BIGINT CHECK (minimum_order_quantity >= 0),
    order_multiple BIGINT CHECK (order_multiple >= 0),
    lead_time_days INTEGER CHECK (lead_time_days >= 0),
    lifecycle VARCHAR,
    region VARCHAR,
    currency VARCHAR,
    source_file_hash VARCHAR,
    ingest_hash VARCHAR NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS price_breaks (
    observation_id UUID NOT NULL REFERENCES observations(observation_id),
    quantity_from BIGINT NOT NULL CHECK (quantity_from >= 1),
    quantity_to BIGINT,
    unit_price DECIMAL(18,6) NOT NULL CHECK (unit_price >= 0),
    currency VARCHAR NOT NULL,
    PRIMARY KEY (observation_id, quantity_from)
);
CREATE TABLE IF NOT EXISTS collection_runs (
    run_id UUID PRIMARY KEY,
    source_id VARCHAR NOT NULL,
    started_at_utc TIMESTAMPTZ NOT NULL,
    completed_at_utc TIMESTAMPTZ NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
    request_count INTEGER NOT NULL CHECK (request_count >= 0),
    success_count INTEGER NOT NULL CHECK (success_count >= 0),
    failure_count INTEGER NOT NULL CHECK (failure_count >= 0),
    error_summary VARCHAR
);
CREATE TABLE IF NOT EXISTS category_signals (
    canonical_category VARCHAR NOT NULL,
    calculated_for DATE NOT NULL,
    observed_at_utc TIMESTAMPTZ NOT NULL,
    source_attribution VARCHAR NOT NULL,
    supplier_category VARCHAR NOT NULL,
    intensity DOUBLE,
    breadth DOUBLE,
    valid_core_count INTEGER NOT NULL,
    configured_core_count INTEGER NOT NULL,
    source_count INTEGER NOT NULL,
    data_status VARCHAR NOT NULL,
    alert_state VARCHAR NOT NULL,
    PRIMARY KEY (canonical_category, calculated_for)
);
"""


class RadarRepository:
    """Writable local authority for permitted normalized data."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        if not read_only:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(self.database_path), read_only=read_only)
        connection.execute("SET TimeZone = 'UTC'")
        return connection

    def initialize(self) -> None:
        """Apply the current idempotent schema migration."""
        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                connection.execute(SCHEMA_SQL)
                connection.execute(
                    "INSERT INTO schema_migrations VALUES (?, ?) ON CONFLICT DO NOTHING",
                    [SCHEMA_VERSION, datetime.now(UTC)],
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def save_observations(
        self, policy: SourcePolicy, observations: tuple[Observation, ...]
    ) -> None:
        """Persist a whole normalized batch or roll it back on any constraint error."""
        require_persistence(policy)
        if any(observation.source_id != policy.source_id for observation in observations):
            raise ValueError("observation source_id must match source policy")
        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                self._upsert_policy(connection, policy)
                for observation in observations:
                    self._insert_observation(connection, observation)
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def _upsert_policy(self, connection: duckdb.DuckDBPyConnection, policy: SourcePolicy) -> None:
        connection.execute(
            """
            INSERT INTO source_policies VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_id) DO UPDATE SET
                persist_allowed = excluded.persist_allowed,
                cloud_share_allowed = excluded.cloud_share_allowed,
                raw_retention_days = excluded.raw_retention_days,
                attribution_required = excluded.attribution_required,
                terms_reviewed_at = excluded.terms_reviewed_at,
                terms_url = excluded.terms_url
            """,
            [
                policy.source_id,
                policy.persist_allowed,
                policy.cloud_share_allowed,
                policy.raw_retention_days,
                policy.attribution_required,
                policy.terms_reviewed_at,
                policy.terms_url,
            ],
        )

    def _insert_observation(
        self, connection: duckdb.DuckDBPyConnection, observation: Observation
    ) -> None:
        exists = connection.execute(
            "SELECT 1 FROM observations WHERE ingest_hash = ?", [observation.ingest_hash]
        ).fetchone()
        if exists is not None:
            return
        observation_id = uuid5(NAMESPACE_URL, observation.ingest_hash)
        connection.execute(
            """
            INSERT INTO observations VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                observation_id,
                observation.source_id,
                observation.mpn,
                observation.manufacturer,
                observation.observed_at_utc,
                observation.supplier_category,
                observation.canonical_category,
                observation.taxonomy_version,
                observation.panel_version,
                observation.panel_role.value,
                observation.quantity_available,
                observation.quantity_factory,
                observation.quantity_on_order,
                observation.minimum_order_quantity,
                observation.order_multiple,
                observation.lead_time_days,
                observation.lifecycle,
                observation.region,
                observation.currency,
                observation.source_file_hash,
                observation.ingest_hash,
            ],
        )
        for price in observation.price_breaks:
            connection.execute(
                "INSERT INTO price_breaks VALUES (?, ?, ?, ?, ?)",
                [
                    observation_id,
                    price.quantity_from,
                    price.quantity_to,
                    price.unit_price,
                    price.currency,
                ],
            )

    def record_run(self, result: RunResult) -> None:
        """Store an audited run separately from observations."""
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO collection_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    uuid4(),
                    result.source_id,
                    result.started_at_utc,
                    result.completed_at_utc,
                    result.status.value,
                    result.request_count,
                    result.success_count,
                    result.failure_count,
                    result.error_summary,
                ],
            )

    def latest_run(self) -> RunResult | None:
        """Return the latest run without exposing arbitrary SQL."""
        with self._connect(read_only=True) as connection:
            row = connection.execute(
                """
                SELECT source_id, status, started_at_utc, completed_at_utc,
                       request_count, success_count, failure_count, error_summary
                FROM collection_runs
                ORDER BY completed_at_utc DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return RunResult(
            source_id=str(row[0]),
            status=RunStatus(str(row[1])),
            started_at_utc=row[2],
            completed_at_utc=row[3],
            request_count=int(row[4]),
            success_count=int(row[5]),
            failure_count=int(row[6]),
            error_summary=None if row[7] is None else str(row[7]),
        )

    def count(self, table: str) -> int:
        """Count rows in a fixed allowlist of repository tables."""
        if table not in COUNTABLE_TABLES:
            raise ValueError("table is not countable")
        with self._connect(read_only=True) as connection:
            row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        if row is None:
            raise RuntimeError("DuckDB count query returned no row")
        return int(row[0])


def decimal_value(value: object) -> Decimal:
    """Narrow a DuckDB decimal value for typed callers."""
    if not isinstance(value, Decimal):
        raise TypeError("DuckDB value is not Decimal")
    return value
