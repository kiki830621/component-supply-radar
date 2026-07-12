from pathlib import Path

import pytest

from component_supply_radar.providers.csv_import import read_observations_csv

HEADER = (
    "mpn,manufacturer,observed_at_utc,supplier_category,canonical_category,"
    "taxonomy_version,panel_version,panel_role,quantity_available,quantity_factory,"
    "quantity_on_order,minimum_order_quantity,order_multiple,lead_time_days,lifecycle,"
    "region,currency,price_quantity_from,price_quantity_to,unit_price\n"
)
ROW = (
    "BAT54STA,onsemi,2026-07-11T00:00:00Z,Schottky Diodes,power-semiconductor,"
    "2026-v1,2026-Q3,core,5000,0,30000,100,100,70,ACTIVE,NA,USD,{quantity_from},"
    "{quantity_to},{unit_price}\n"
)


def write_csv(path: Path, rows: list[str]) -> None:
    path.write_text(HEADER + "".join(rows), encoding="utf-8")


def test_csv_rows_form_one_observation_with_two_price_breaks(tmp_path: Path) -> None:
    path = tmp_path / "observations.csv"
    write_csv(
        path,
        [
            ROW.format(quantity_from=100, quantity_to=199, unit_price="0.218"),
            ROW.format(quantity_from=200, quantity_to="", unit_price="0.190"),
        ],
    )

    observations = read_observations_csv(path, "owned_csv")

    assert len(observations) == 1
    assert [price.quantity_from for price in observations[0].price_breaks] == [100, 200]
    assert observations[0].ingest_hash == read_observations_csv(path, "owned_csv")[0].ingest_hash


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (",5000,0,", ",-1,0,", "negative"),
        ("2026-07-11T00:00:00Z", "2026-07-11T00:00:00", "UTC"),
        (",USD,", ",usd,", "currency"),
    ],
)
def test_csv_rejects_invalid_boundaries(tmp_path: Path, old: str, new: str, message: str) -> None:
    path = tmp_path / "invalid.csv"
    write_csv(path, [ROW.format(quantity_from=100, quantity_to="", unit_price="0.218")])
    path.write_text(path.read_text().replace(old, new), encoding="utf-8")

    with pytest.raises((TypeError, ValueError), match=message):
        read_observations_csv(path, "owned_csv")


def test_csv_rejects_conflicting_duplicate_observation_fields(tmp_path: Path) -> None:
    path = tmp_path / "conflict.csv"
    first = ROW.format(quantity_from=100, quantity_to=199, unit_price="0.218")
    second = ROW.format(quantity_from=200, quantity_to="", unit_price="0.190").replace(
        ",5000,0,", ",4000,0,"
    )
    write_csv(path, [first, second])

    with pytest.raises(ValueError, match="conflicting"):
        read_observations_csv(path, "owned_csv")
