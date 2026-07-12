from dataclasses import replace
from datetime import date
from pathlib import Path

import duckdb
import pytest

from component_supply_radar.policy import SourcePolicy
from component_supply_radar.storage import RadarRepository
from component_supply_radar.sync import SyncError, publish_to_motherduck
from tests.test_storage import observation, policy


def test_sync_publishes_only_cloud_allowed_sources(tmp_path: Path) -> None:
    repository = RadarRepository(tmp_path / "radar.duckdb")
    repository.initialize()
    repository.save_observations(policy(), (observation(),))
    private_policy = SourcePolicy(
        "private_csv",
        True,
        False,
        0,
        False,
        date(2026, 7, 11),
        "https://example.com/terms",
    )
    private_observation = replace(observation(ingest_hash="b" * 64), source_id="private_csv")
    repository.save_observations(private_policy, (private_observation,))
    target = tmp_path / "motherduck.duckdb"

    result = publish_to_motherduck(
        repository,
        token="secret",
        database_name="radar",
        connect_target=lambda _database, _token: duckdb.connect(str(target)),
    )

    assert result.status == "success"
    with duckdb.connect(str(target), read_only=True) as connection:
        sources = connection.execute("SELECT DISTINCT source_id FROM observations").fetchall()
        prices = connection.execute("SELECT COUNT(*) FROM price_breaks").fetchone()[0]
    assert sources == [("future",)]
    assert prices == 1


def test_sync_without_token_is_skipped_and_local_work_remains(tmp_path: Path) -> None:
    repository = RadarRepository(tmp_path / "radar.duckdb")
    repository.initialize()

    result = publish_to_motherduck(repository, token=None, database_name="radar")

    assert result.status == "skipped"
    assert repository.count("observations") == 0


def test_sync_failure_does_not_change_local_authority(tmp_path: Path) -> None:
    repository = RadarRepository(tmp_path / "radar.duckdb")
    repository.initialize()
    repository.save_observations(policy(), (observation(),))

    def fail(_database: str, _token: str) -> duckdb.DuckDBPyConnection:
        raise RuntimeError("remote unavailable")

    with pytest.raises(SyncError, match="publication failed"):
        publish_to_motherduck(
            repository,
            token="secret",
            database_name="radar",
            connect_target=fail,
        )

    assert repository.count("observations") == 1
