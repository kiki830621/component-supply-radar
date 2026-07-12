"""Authorized supplier CSV normalization."""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TypedDict

from component_supply_radar.models import Observation, PanelRole, PriceBreak
from component_supply_radar.normalization import canonical_hash

BASE_FIELDS = (
    "mpn",
    "manufacturer",
    "observed_at_utc",
    "supplier_category",
    "canonical_category",
    "taxonomy_version",
    "panel_version",
    "panel_role",
    "quantity_available",
    "quantity_factory",
    "quantity_on_order",
    "minimum_order_quantity",
    "order_multiple",
    "lead_time_days",
    "lifecycle",
    "region",
    "currency",
)
PRICE_FIELDS = ("price_quantity_from", "price_quantity_to", "unit_price")
REQUIRED_COLUMNS = set(BASE_FIELDS + PRICE_FIELDS)


class PricePayload(TypedDict):
    quantity_from: int
    quantity_to: int | None
    unit_price: Decimal
    currency: str


def _optional_int(value: str, field_name: str) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError as error:
        raise ValueError(f"{field_name} must be an integer") from error


def _required_int(value: str, field_name: str) -> int:
    parsed = _optional_int(value, field_name)
    if parsed is None:
        raise ValueError(f"{field_name} must not be empty")
    return parsed


def _timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("observed_at_utc must be an ISO 8601 timestamp") from error


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except InvalidOperation as error:
        raise ValueError("unit_price must be decimal") from error


def _base_payload(row: dict[str, str], source_id: str) -> dict[str, object]:
    return {
        "source_id": source_id,
        "mpn": row["mpn"].strip(),
        "manufacturer": row["manufacturer"].strip(),
        "observed_at_utc": _timestamp(row["observed_at_utc"]),
        "supplier_category": row["supplier_category"].strip(),
        "canonical_category": row["canonical_category"].strip(),
        "taxonomy_version": row["taxonomy_version"].strip(),
        "panel_version": row["panel_version"].strip(),
        "panel_role": PanelRole(row["panel_role"].strip().lower()),
        "quantity_available": _optional_int(row["quantity_available"], "quantity_available"),
        "quantity_factory": _optional_int(row["quantity_factory"], "quantity_factory"),
        "quantity_on_order": _optional_int(row["quantity_on_order"], "quantity_on_order"),
        "minimum_order_quantity": _optional_int(
            row["minimum_order_quantity"], "minimum_order_quantity"
        ),
        "order_multiple": _optional_int(row["order_multiple"], "order_multiple"),
        "lead_time_days": _optional_int(row["lead_time_days"], "lead_time_days"),
        "lifecycle": row["lifecycle"].strip() or None,
        "region": row["region"].strip() or None,
        "currency": row["currency"].strip() or None,
    }


def _price_payload(row: dict[str, str]) -> PricePayload:
    return {
        "quantity_from": _required_int(row["price_quantity_from"], "price_quantity_from"),
        "quantity_to": _optional_int(row["price_quantity_to"], "price_quantity_to"),
        "unit_price": _decimal(row["unit_price"]),
        "currency": row["currency"].strip(),
    }


def read_observations_csv(path: Path, source_id: str) -> tuple[Observation, ...]:
    """Read authorized observations while retaining a source file audit hash."""
    if not source_id.strip():
        raise ValueError("source_id must not be empty")
    file_bytes = path.read_bytes()
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    groups: dict[tuple[str, str], list[tuple[dict[str, object], PricePayload]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            base = _base_payload(row, source_id)
            identity = (str(base["mpn"]), str(base["observed_at_utc"]))
            groups[identity].append((base, _price_payload(row)))

    observations: list[Observation] = []
    for rows in groups.values():
        base = rows[0][0]
        if any(candidate != base for candidate, _ in rows[1:]):
            raise ValueError(f"conflicting duplicate fields for {base['mpn']}")
        prices = [price for _, price in rows]
        quantities = [price["quantity_from"] for price in prices]
        if len(quantities) != len(set(quantities)):
            raise ValueError(f"duplicate price quantity for {base['mpn']}")
        prices.sort(key=lambda price: price["quantity_from"])
        ingest_hash = canonical_hash(base, prices)
        price_breaks = tuple(PriceBreak(**price) for price in prices)
        observations.append(
            Observation(
                **base,  # type: ignore[arg-type]
                price_breaks=price_breaks,
                source_file_hash=file_hash,
                ingest_hash=ingest_hash,
            )
        )
    return tuple(observations)
