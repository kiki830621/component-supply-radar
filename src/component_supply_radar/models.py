"""Normalized immutable domain records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal


class PanelRole(StrEnum):
    CORE = "core"
    EXPLORATORY = "exploratory"


class RunStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class DataStatus(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


class AlertState(StrEnum):
    NORMAL = "normal"
    WATCH = "watch"
    CONFIRMED = "confirmed"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use UTC")


def _require_nonnegative(value: int | None, field_name: str) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{field_name} must not be negative")


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_currency(value: str) -> None:
    if len(value) != 3 or not value.isalpha() or not value.isupper():
        raise ValueError("currency must be a three-letter uppercase code")


@dataclass(frozen=True, slots=True)
class PriceBreak:
    quantity_from: int
    quantity_to: int | None
    unit_price: Decimal
    currency: str

    def __post_init__(self) -> None:
        _require_nonnegative(self.quantity_from, "quantity_from")
        if self.quantity_from < 1:
            raise ValueError("quantity_from must be at least one")
        _require_nonnegative(self.quantity_to, "quantity_to")
        if self.quantity_to is not None and self.quantity_to < self.quantity_from:
            raise ValueError("quantity_to must not be lower than quantity_from")
        if not isinstance(self.unit_price, Decimal):
            raise TypeError("unit_price must be Decimal")
        if self.unit_price < 0:
            raise ValueError("unit_price must not be negative")
        _require_currency(self.currency)


@dataclass(frozen=True, slots=True)
class PanelMember:
    mpn: str
    manufacturer: str
    supplier_category: str
    canonical_category: str
    taxonomy_version: str
    panel_version: str
    role: PanelRole
    active: bool

    def __post_init__(self) -> None:
        for field_name in (
            "mpn",
            "manufacturer",
            "supplier_category",
            "canonical_category",
            "taxonomy_version",
            "panel_version",
        ):
            _require_text(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class Observation:
    source_id: str
    mpn: str
    manufacturer: str
    observed_at_utc: datetime
    supplier_category: str
    canonical_category: str
    taxonomy_version: str
    panel_version: str
    panel_role: PanelRole
    quantity_available: int | None
    quantity_factory: int | None
    quantity_on_order: int | None
    minimum_order_quantity: int | None
    order_multiple: int | None
    lead_time_days: int | None
    lifecycle: str | None
    region: str | None
    currency: str | None
    price_breaks: tuple[PriceBreak, ...]
    source_file_hash: str | None
    ingest_hash: str

    def __post_init__(self) -> None:
        for field_name in (
            "source_id",
            "mpn",
            "manufacturer",
            "supplier_category",
            "canonical_category",
            "taxonomy_version",
            "panel_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_utc(self.observed_at_utc, "observed_at_utc")
        for field_name in (
            "quantity_available",
            "quantity_factory",
            "quantity_on_order",
            "minimum_order_quantity",
            "order_multiple",
            "lead_time_days",
        ):
            _require_nonnegative(getattr(self, field_name), field_name)
        if self.currency is not None:
            _require_currency(self.currency)
        if len(self.ingest_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.ingest_hash
        ):
            raise ValueError("ingest_hash must be a lowercase SHA-256 hex digest")
        if self.source_file_hash is not None and (
            len(self.source_file_hash) != 64
            or any(character not in "0123456789abcdef" for character in self.source_file_hash)
        ):
            raise ValueError("source_file_hash must be a lowercase SHA-256 hex digest")
        if self.currency is not None and any(
            price.currency != self.currency for price in self.price_breaks
        ):
            raise ValueError("price break currency must match observation currency")


@dataclass(frozen=True, slots=True)
class DirectExposure:
    manufacturer: str
    ticker: str
    mapping_version: str
    reviewed_by: str
    reviewed_at_utc: datetime
    evidence_ref: str

    def __post_init__(self) -> None:
        for field_name in (
            "manufacturer",
            "ticker",
            "mapping_version",
            "reviewed_by",
            "evidence_ref",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_utc(self.reviewed_at_utc, "reviewed_at_utc")


@dataclass(frozen=True, slots=True)
class ThematicExposure:
    canonical_category: str
    ticker: str
    relationship: Literal["upstream", "downstream", "alternative-supplier"]
    mapping_version: str
    reviewed_by: str
    reviewed_at_utc: datetime
    evidence_ref: str

    def __post_init__(self) -> None:
        for field_name in (
            "canonical_category",
            "ticker",
            "mapping_version",
            "reviewed_by",
            "evidence_ref",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.relationship not in {"upstream", "downstream", "alternative-supplier"}:
            raise ValueError("relationship is invalid")
        _require_utc(self.reviewed_at_utc, "reviewed_at_utc")


@dataclass(frozen=True, slots=True)
class RunResult:
    source_id: str
    status: RunStatus
    started_at_utc: datetime
    completed_at_utc: datetime
    request_count: int
    success_count: int
    failure_count: int
    error_summary: str | None

    def __post_init__(self) -> None:
        _require_text(self.source_id, "source_id")
        _require_utc(self.started_at_utc, "started_at_utc")
        _require_utc(self.completed_at_utc, "completed_at_utc")
        if self.completed_at_utc < self.started_at_utc:
            raise ValueError("completed_at_utc must not be before started_at_utc")
        for field_name in ("request_count", "success_count", "failure_count"):
            _require_nonnegative(getattr(self, field_name), field_name)
