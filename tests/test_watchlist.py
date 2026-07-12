from pathlib import Path

import pytest

from component_supply_radar.models import PanelRole
from component_supply_radar.watchlist import active_members, load_watchlist, official_core_members


def write_watchlist(path: Path) -> None:
    path.write_text(
        "mpn,manufacturer,supplier_category,canonical_category,taxonomy_version,"
        "panel_version,role,active\n"
        "BAT54STA,onsemi,Schottky Diodes,power-semiconductor,2026-v1,2026-Q3,core,true\n"
        "LM358,Texas Instruments,Operational Amplifiers,analog-ic,2026-v1,2026-Q3,"
        "exploratory,true\n"
        "OLD1,Example,Legacy Diodes,power-semiconductor,2026-v1,2026-Q3,core,false\n",
        encoding="utf-8",
    )


def test_exploratory_member_is_excluded_from_official_panel(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.csv"
    write_watchlist(path)

    members = load_watchlist(path)

    assert [member.mpn for member in active_members(members)] == ["BAT54STA", "LM358"]
    assert [member.mpn for member in official_core_members(members)] == ["BAT54STA"]
    assert members[1].role is PanelRole.EXPLORATORY


def test_watchlist_retains_raw_canonical_and_taxonomy_version(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.csv"
    write_watchlist(path)

    member = load_watchlist(path)[0]

    assert member.supplier_category == "Schottky Diodes"
    assert member.canonical_category == "power-semiconductor"
    assert member.taxonomy_version == "2026-v1"


def test_watchlist_rejects_unknown_role(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.csv"
    write_watchlist(path)
    path.write_text(path.read_text().replace("exploratory", "dynamic"), encoding="utf-8")

    with pytest.raises(ValueError, match="role"):
        load_watchlist(path)
