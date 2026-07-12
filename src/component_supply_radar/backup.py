"""Atomic Parquet snapshot export and bounded retention."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import duckdb

from component_supply_radar.storage import RadarRepository

SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _complete_snapshots(root: Path) -> list[Path]:
    return sorted(
        path for path in root.iterdir() if path.is_dir() and (path / "manifest.json").is_file()
    )


def create_backup(
    repository: RadarRepository,
    backup_root: Path,
    *,
    now: datetime,
    keep: int = 12,
) -> Path:
    """Create a complete Parquet snapshot before applying retention."""
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("backup time must use UTC")
    if keep < 1:
        raise ValueError("keep must be at least one")
    backup_root.mkdir(parents=True, exist_ok=True)
    name = now.strftime("%Y-%m-%dT%H%M%SZ")
    destination = backup_root / name
    if destination.exists():
        raise FileExistsError(f"backup already exists: {destination}")
    temporary = backup_root / f".{name}.tmp-{uuid4().hex}"
    temporary.mkdir()
    try:
        with duckdb.connect(str(repository.database_path), read_only=True) as connection:
            connection.execute("SET TimeZone = 'UTC'")
            table_rows = connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main' AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            ).fetchall()
            tables = [str(row[0]) for row in table_rows]
            for table in tables:
                if SAFE_IDENTIFIER.fullmatch(table) is None:
                    raise ValueError(f"unsafe DuckDB table identifier: {table}")
                output = temporary / f"{table}.parquet"
                connection.execute(
                    f"COPY (SELECT * FROM \"{table}\") TO '{_sql_path(output)}' "
                    "(FORMAT PARQUET, COMPRESSION ZSTD)"
                )
            version_row = connection.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()
        if version_row is None or version_row[0] is None:
            raise RuntimeError("database has no schema version")
        manifest = {
            "schema_version": int(version_row[0]),
            "exported_at_utc": now.isoformat(),
            "source_database": repository.database_path.name,
            "tables": tables,
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    complete = _complete_snapshots(backup_root)
    for old_snapshot in complete[:-keep]:
        shutil.rmtree(old_snapshot)
    return destination
