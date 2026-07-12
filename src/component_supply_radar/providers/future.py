"""Licensed Future Electronics Product Info API adapter."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import cast

import httpx

from component_supply_radar.models import Observation, PanelMember, PriceBreak
from component_supply_radar.normalization import canonical_hash

BATCH_SIZE = 300
DEFAULT_BASE_URL = "https://api.futureelectronics.com"
BATCH_PATH = "/api/v1/pim-future/batch/lookup"
AUTH_STATUSES = {401, 402, 403, 406}


class ProviderError(RuntimeError):
    """Base error for supplier failures."""


class ProviderAuthError(ProviderError):
    """A terminal authentication or license failure."""


class ProviderRateLimitError(ProviderError):
    """A retryable supplier rate limit."""


class ProviderTransientError(ProviderError):
    """A retryable network or server failure."""


class ProviderResponseError(ProviderError):
    """A non-retryable malformed response."""


def _chunks[T](values: Sequence[T], size: int) -> Iterable[Sequence[T]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProviderResponseError(f"Future response field {field_name} must be an object")
    return cast(Mapping[str, object], value)


def _list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise ProviderResponseError(f"Future response field {field_name} must be an array")
    return value


def _optional_int(value: object, field_name: str) -> int | None:
    if value is None or value == "" or str(value).upper() == "N/A":
        return None
    if isinstance(value, bool):
        raise ProviderResponseError(f"Future response field {field_name} must be numeric")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ProviderResponseError(f"Future response field {field_name} must be an integer")
        return int(value)
    if not isinstance(value, str):
        raise ProviderResponseError(f"Future response field {field_name} must be numeric")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        message = f"Future response field {field_name} must be numeric"
        raise ProviderResponseError(message) from error


def _lead_time_days(quantities: Mapping[str, object]) -> int | None:
    value = _optional_int(quantities.get("factory_leadtime"), "factory_leadtime")
    if value is None:
        return None
    units = str(quantities.get("factory_leadtime_units", "")).strip().lower()
    if units in {"week", "weeks"}:
        return value * 7
    if units in {"day", "days"}:
        return value
    raise ProviderResponseError("Future response has unsupported factory lead-time units")


def _attributes(offer: Mapping[str, object]) -> dict[str, object]:
    attributes: dict[str, object] = {}
    for raw_attribute in _list(offer.get("part_attributes", []), "part_attributes"):
        attribute = _mapping(raw_attribute, "part_attributes[]")
        name = attribute.get("name")
        if isinstance(name, str):
            attributes[name] = attribute.get("value")
    return attributes


def _supplier_category(offer: Mapping[str, object], fallback: str) -> str:
    categories = _list(offer.get("categories", []), "categories")
    if not categories:
        return fallback
    category = _mapping(categories[0], "categories[0]")
    for key in ("name", "type_name", "subcategory_name"):
        value = category.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _price_breaks(offer: Mapping[str, object], currency: str) -> tuple[PriceBreak, ...]:
    prices: list[PriceBreak] = []
    for raw_price in _list(offer.get("pricing", []), "pricing"):
        price = _mapping(raw_price, "pricing[]")
        quantity_from = _optional_int(price.get("quantity_from"), "quantity_from")
        if quantity_from is None:
            raise ProviderResponseError("Future price is missing quantity_from")
        try:
            unit_price = Decimal(str(price["unit_price"]))
        except (KeyError, ValueError) as error:
            raise ProviderResponseError("Future price is missing a valid unit_price") from error
        prices.append(
            PriceBreak(
                quantity_from=quantity_from,
                quantity_to=_optional_int(price.get("quantity_to"), "quantity_to"),
                unit_price=unit_price,
                currency=currency,
            )
        )
    return tuple(sorted(prices, key=lambda item: item.quantity_from))


class FutureClient:
    """Fetch only explicitly configured MPNs from Future Electronics."""

    source_id = "future"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Future API key must not be empty")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=5.0),
            headers={"User-Agent": "component-supply-radar/0.1"},
        )
        self.last_request_count = 0

    def __repr__(self) -> str:
        return f"FutureClient(base_url={self._base_url!r})"

    def collect(
        self, members: Sequence[PanelMember], observed_at_utc: datetime
    ) -> tuple[Observation, ...]:
        """Collect active panel members in bounded batches."""
        active = [member for member in members if member.active]
        self.last_request_count = 0
        if not active:
            return ()
        observations: list[Observation] = []
        for batch in _chunks(active, BATCH_SIZE):
            self.last_request_count += 1
            response = self._request_batch([member.mpn for member in batch])
            observations.extend(self._normalize(response, batch, observed_at_utc))
        return tuple(observations)

    def _request_batch(self, mpns: list[str]) -> Mapping[str, object]:
        try:
            response = self._client.post(
                f"{self._base_url}{BATCH_PATH}",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "x-orbweaver-licensekey": self._api_key,
                },
                json={"parts": mpns},
            )
        except httpx.HTTPError as error:
            raise ProviderTransientError("Future request failed") from error
        if response.status_code in AUTH_STATUSES:
            raise ProviderAuthError("Future authorization or license was rejected")
        if response.status_code == 429:
            raise ProviderRateLimitError("Future rate limit reached")
        if response.status_code >= 500:
            raise ProviderTransientError("Future server failed")
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ProviderResponseError("Future returned an invalid response") from error
        return _mapping(payload, "root")

    def _normalize(
        self,
        payload: Mapping[str, object],
        batch: Sequence[PanelMember],
        observed_at_utc: datetime,
    ) -> list[Observation]:
        configured = {member.mpn: member for member in batch}
        observations: list[Observation] = []
        for raw_lookup in _list(payload.get("lookup_parts", []), "lookup_parts"):
            lookup = _mapping(raw_lookup, "lookup_parts[]")
            requested_mpn = str(lookup.get("part_number", ""))
            member = configured.get(requested_mpn)
            if member is None:
                continue
            for raw_offer in _list(lookup.get("offers", []), "offers"):
                offer = _mapping(raw_offer, "offers[]")
                observations.append(self._normalize_offer(offer, member, observed_at_utc))
        return observations

    def _normalize_offer(
        self,
        offer: Mapping[str, object],
        member: PanelMember,
        observed_at_utc: datetime,
    ) -> Observation:
        attributes = _attributes(offer)
        quantities = _mapping(offer.get("quantities", {}), "quantities")
        places = _mapping(offer.get("people_and_places", {}), "people_and_places")
        currency_block = _mapping(offer.get("currency", {}), "currency")
        currency = str(currency_block.get("currency_code", "")).upper()
        prices = _price_breaks(offer, currency)
        base: dict[str, object] = {
            "source_id": "future",
            "mpn": member.mpn,
            "manufacturer": str(attributes.get("manufacturerName") or member.manufacturer),
            "observed_at_utc": observed_at_utc,
            "supplier_category": _supplier_category(offer, member.supplier_category),
            "canonical_category": member.canonical_category,
            "taxonomy_version": member.taxonomy_version,
            "panel_version": member.panel_version,
            "panel_role": member.role,
            "quantity_available": _optional_int(
                quantities.get("quantity_available"), "quantity_available"
            ),
            "quantity_factory": _optional_int(
                quantities.get("quantity_factory"), "quantity_factory"
            ),
            "quantity_on_order": _optional_int(
                quantities.get("quantity_on_order"), "quantity_on_order"
            ),
            "minimum_order_quantity": _optional_int(
                quantities.get("quantity_minimum"), "quantity_minimum"
            ),
            "order_multiple": _optional_int(quantities.get("order_mult_qty"), "order_mult_qty"),
            "lead_time_days": _lead_time_days(quantities),
            "lifecycle": str(attributes.get("productLifeCycle") or "") or None,
            "region": str(places.get("site") or "") or None,
            "currency": currency or None,
        }
        price_payloads = [
            {
                "quantity_from": price.quantity_from,
                "quantity_to": price.quantity_to,
                "unit_price": price.unit_price,
                "currency": price.currency,
            }
            for price in prices
        ]
        return Observation(
            **base,  # type: ignore[arg-type]
            price_breaks=prices,
            source_file_hash=None,
            ingest_hash=canonical_hash(base, price_payloads),
        )
