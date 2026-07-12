"""Versioned core and exploratory watch panel loading."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from component_supply_radar.models import PanelMember, PanelRole

REQUIRED_COLUMNS = {
    "mpn",
    "manufacturer",
    "supplier_category",
    "canonical_category",
    "taxonomy_version",
    "panel_version",
    "role",
    "active",
}


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("active must be true or false")


def _parse_role(value: str) -> PanelRole:
    try:
        return PanelRole(value.strip().lower())
    except ValueError as error:
        raise ValueError("role must be core or exploratory") from error


def load_watchlist(path: Path) -> tuple[PanelMember, ...]:
    """Load a complete versioned watch panel without enumerating a supplier catalog."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"watchlist is missing columns: {', '.join(sorted(missing))}")
        members: list[PanelMember] = []
        seen: set[tuple[str, str, str]] = set()
        for row in reader:
            member = PanelMember(
                mpn=row["mpn"].strip(),
                manufacturer=row["manufacturer"].strip(),
                supplier_category=row["supplier_category"].strip(),
                canonical_category=row["canonical_category"].strip(),
                taxonomy_version=row["taxonomy_version"].strip(),
                panel_version=row["panel_version"].strip(),
                role=_parse_role(row["role"]),
                active=_parse_bool(row["active"]),
            )
            identity = (member.mpn, member.manufacturer, member.panel_version)
            if identity in seen:
                raise ValueError(f"duplicate watchlist member: {member.mpn}")
            seen.add(identity)
            members.append(member)
    return tuple(members)


def active_members(members: Iterable[PanelMember]) -> tuple[PanelMember, ...]:
    """Return only configured active members for supplier requests."""
    return tuple(member for member in members if member.active)


def official_core_members(members: Iterable[PanelMember]) -> tuple[PanelMember, ...]:
    """Return active core members eligible for official category indices."""
    return tuple(member for member in members if member.active and member.role is PanelRole.CORE)
