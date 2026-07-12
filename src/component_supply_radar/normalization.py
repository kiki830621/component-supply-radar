"""Deterministic normalization helpers shared by ingestion adapters."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, Decimal)):
        return str(value)
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_hash(
    payload: Mapping[str, object], price_breaks: Sequence[Mapping[str, object]]
) -> str:
    """Hash normalized content without depending on input file formatting."""
    canonical = {**payload, "price_breaks": list(price_breaks)}
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
