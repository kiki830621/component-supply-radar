import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

from component_supply_radar.backup import create_backup
from component_supply_radar.storage import SCHEMA_VERSION, RadarRepository


def test_thirteenth_backup_retains_twelve_complete_snapshots(tmp_path: Path) -> None:
    repository = RadarRepository(tmp_path / "radar.duckdb")
    repository.initialize()
    backup_root = tmp_path / "backups"
    start = datetime(2026, 1, 1, tzinfo=UTC)

    paths = [
        create_backup(repository, backup_root, now=start + timedelta(weeks=index), keep=12)
        for index in range(13)
    ]

    complete = sorted(path for path in backup_root.iterdir() if (path / "manifest.json").exists())
    assert len(complete) == 12
    assert not paths[0].exists()
    assert paths[-1].exists()


def test_backup_manifest_and_parquet_are_readable(tmp_path: Path) -> None:
    repository = RadarRepository(tmp_path / "radar.duckdb")
    repository.initialize()
    exported_at = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)

    snapshot = create_backup(repository, tmp_path / "backups", now=exported_at)

    manifest = json.loads((snapshot / "manifest.json").read_text())
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["exported_at_utc"] == "2026-07-11T00:00:00+00:00"
    assert "observations" in manifest["tables"]
    with duckdb.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM read_parquet(?)", [str(snapshot / "observations.parquet")]
        ).fetchone()[0]
    assert count == 0
