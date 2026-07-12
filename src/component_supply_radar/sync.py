"""Policy-gated one-way publication to MotherDuck."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import duckdb

from component_supply_radar.storage import RadarRepository

SAFE_DATABASE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ConnectTarget = Callable[[str, str], duckdb.DuckDBPyConnection]


class SyncError(RuntimeError):
    """Raised when cloud publication fails without changing local data."""


@dataclass(frozen=True, slots=True)
class SyncResult:
    status: str
    published_observations: int


def _default_connect(database_name: str, token: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(
        f"md:{database_name}",
        config={"motherduck_token": token},
    )


def _sql_path(value: str) -> str:
    return value.replace("'", "''")


def publish_to_motherduck(
    repository: RadarRepository,
    *,
    token: str | None,
    database_name: str,
    connect_target: ConnectTarget = _default_connect,
) -> SyncResult:
    """Replace the sharing copy with only cloud-authorized source rows."""
    if token is None:
        return SyncResult("skipped", 0)
    if not token.strip():
        raise ValueError("MotherDuck token must not be empty")
    if SAFE_DATABASE.fullmatch(database_name) is None:
        raise ValueError("MotherDuck database name is invalid")
    source_path = _sql_path(str(repository.database_path))
    try:
        with connect_target(database_name, token) as connection:
            connection.execute(f"ATTACH '{source_path}' AS radar_source (READ_ONLY)")
            connection.execute("BEGIN")
            try:
                connection.execute(
                    """
                    CREATE OR REPLACE TABLE source_policies AS
                    SELECT * FROM radar_source.source_policies
                    WHERE cloud_share_allowed = true
                    """
                )
                connection.execute(
                    """
                    CREATE OR REPLACE TABLE observations AS
                    SELECT observation.*
                    FROM radar_source.observations AS observation
                    JOIN radar_source.source_policies AS policy USING (source_id)
                    WHERE policy.cloud_share_allowed = true
                    """
                )
                connection.execute(
                    """
                    CREATE OR REPLACE TABLE price_breaks AS
                    SELECT price.*
                    FROM radar_source.price_breaks AS price
                    JOIN radar_source.observations AS observation USING (observation_id)
                    JOIN radar_source.source_policies AS policy USING (source_id)
                    WHERE policy.cloud_share_allowed = true
                    """
                )
                connection.execute(
                    """
                    CREATE OR REPLACE TABLE collection_runs AS
                    SELECT run.*
                    FROM radar_source.collection_runs AS run
                    JOIN radar_source.source_policies AS policy USING (source_id)
                    WHERE policy.cloud_share_allowed = true
                    """
                )
                row = connection.execute("SELECT COUNT(*) FROM observations").fetchone()
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            finally:
                connection.execute("DETACH radar_source")
    except Exception as error:
        raise SyncError("MotherDuck publication failed") from error
    if row is None:
        raise SyncError("MotherDuck publication returned no count")
    return SyncResult("success", int(row[0]))
