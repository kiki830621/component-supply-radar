from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from component_supply_radar.models import Observation, PanelRole, PriceBreak, RunResult, RunStatus
from component_supply_radar.policy import PersistenceForbidden, SourcePolicy
from component_supply_radar.storage import RadarRepository

NOW = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)


def policy(*, allowed: bool = True) -> SourcePolicy:
    return SourcePolicy(
        "future",
        allowed,
        True,
        0,
        True,
        date(2026, 7, 11),
        "https://www.futureelectronics.com/fr/api-solutions",
    )


def observation(*, ingest_hash: str = "a" * 64) -> Observation:
    return Observation(
        "future",
        "BAT54STA",
        "onsemi",
        NOW,
        "Schottky Diodes",
        "power-semiconductor",
        "2026-v1",
        "2026-Q3",
        PanelRole.CORE,
        5000,
        0,
        30000,
        100,
        100,
        70,
        "ACTIVE",
        "NA",
        "USD",
        (PriceBreak(100, None, Decimal("0.218000"), "USD"),),
        None,
        ingest_hash,
    )


def test_save_observation_is_idempotent_and_prices_are_decimal(tmp_path: Path) -> None:
    database = tmp_path / "radar.duckdb"
    repository = RadarRepository(database)
    repository.initialize()

    repository.save_observations(policy(), (observation(),))
    repository.save_observations(policy(), (observation(),))

    assert repository.count("observations") == 1
    assert repository.count("price_breaks") == 1
    with duckdb.connect(str(database), read_only=True) as connection:
        price = connection.execute("SELECT unit_price FROM price_breaks").fetchone()[0]
        column_type = connection.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'price_breaks' AND column_name = 'unit_price'"
        ).fetchone()[0]
    assert price == Decimal("0.218000")
    assert column_type == "DECIMAL(18,6)"


def test_transaction_rolls_back_invalid_batch(tmp_path: Path) -> None:
    repository = RadarRepository(tmp_path / "radar.duckdb")
    repository.initialize()
    duplicate_prices = (
        PriceBreak(100, 199, Decimal("0.218"), "USD"),
        PriceBreak(100, None, Decimal("0.190"), "USD"),
    )
    invalid_for_storage = replace(observation(ingest_hash="b" * 64), price_breaks=duplicate_prices)

    with pytest.raises(duckdb.ConstraintException):
        repository.save_observations(policy(), (observation(), invalid_for_storage))

    assert repository.count("observations") == 0
    assert repository.count("price_breaks") == 0


def test_repository_rechecks_persistence_policy(tmp_path: Path) -> None:
    repository = RadarRepository(tmp_path / "radar.duckdb")
    repository.initialize()

    with pytest.raises(PersistenceForbidden):
        repository.save_observations(policy(allowed=False), (observation(),))

    assert repository.count("observations") == 0


def test_record_run_keeps_times_counts_and_status(tmp_path: Path) -> None:
    repository = RadarRepository(tmp_path / "radar.duckdb")
    repository.initialize()
    result = RunResult("future", RunStatus.PARTIAL, NOW, NOW, 2, 1, 1, "one missing")

    repository.record_run(result)

    assert repository.count("collection_runs") == 1
    assert repository.latest_run() == result
