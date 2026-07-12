"""Machine-readable supplier data rights and mandatory sink guards."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date


class PersistenceForbidden(RuntimeError):
    """Raised before data reaches a sink that the source policy forbids."""


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    """Rights that must be explicit before data is persisted or shared."""

    source_id: str
    persist_allowed: bool
    cloud_share_allowed: bool
    raw_retention_days: int
    attribution_required: bool
    terms_reviewed_at: date
    terms_url: str

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty")
        if self.raw_retention_days < 0:
            raise ValueError("raw_retention_days must not be negative")
        if not self.terms_url.startswith("https://"):
            raise ValueError("terms_url must use https")


def require_persistence(policy: SourcePolicy) -> None:
    """Fail loudly when a source has not granted persistence rights."""
    if not policy.persist_allowed:
        raise PersistenceForbidden(f"persistence is forbidden for source {policy.source_id}")


def persist_with_policy[T](policy: SourcePolicy, sink: Callable[[], T]) -> T:
    """Call a persistent sink only after enforcing the source policy."""
    require_persistence(policy)
    return sink()
