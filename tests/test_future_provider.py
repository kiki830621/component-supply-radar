import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from component_supply_radar.models import PanelMember, PanelRole
from component_supply_radar.providers.future import (
    FutureClient,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTransientError,
)

NOW = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)


def member(index: int = 0, *, active: bool = True) -> PanelMember:
    return PanelMember(
        mpn="BAT54STA" if index == 0 else f"PART-{index:04d}",
        manufacturer="onsemi",
        supplier_category="Configured Category",
        canonical_category="power-semiconductor",
        taxonomy_version="2026-v1",
        panel_version="2026-Q3",
        role=PanelRole.CORE,
        active=active,
    )


def fixture(name: str) -> dict[str, object]:
    return json.loads((Path(__file__).parent / "fixtures" / name).read_text())


def test_future_batch_normalizes_inventory_lead_time_and_prices(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json=fixture("future_batch.json"))
    client = FutureClient("future-secret", base_url="https://api.future.test")

    observations = client.collect([member()], NOW)

    observation = observations[0]
    assert observation.quantity_available == 5000
    assert observation.quantity_on_order == 30000
    assert observation.lead_time_days == 70
    assert observation.supplier_category == "Schottky Diodes"
    assert observation.canonical_category == "power-semiconductor"
    assert observation.price_breaks[0].unit_price == Decimal("0.218")
    assert "future-secret" not in repr(client)


def test_future_batches_650_active_parts_in_groups_of_at_most_300(
    httpx_mock: HTTPXMock,
) -> None:
    for _ in range(3):
        httpx_mock.add_response(json={"lookup_parts": []})
    client = FutureClient("secret", base_url="https://api.future.test")

    assert client.collect([member(index) for index in range(1, 651)], NOW) == ()

    sizes = [len(json.loads(request.content)["parts"]) for request in httpx_mock.get_requests()]
    assert sizes == [300, 300, 50]


def test_future_does_not_query_inactive_member(httpx_mock: HTTPXMock) -> None:
    client = FutureClient("secret", base_url="https://api.future.test")

    assert client.collect([member(active=False)], NOW) == ()
    assert httpx_mock.get_requests() == []


@pytest.mark.parametrize("status", [401, 402, 403, 406])
def test_future_classifies_license_status_as_terminal(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(status_code=status)

    with pytest.raises(ProviderAuthError, match="Future authorization"):
        FutureClient("secret", base_url="https://api.future.test").collect([member()], NOW)


def test_future_classifies_rate_limit_and_server_failure(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(status_code=429)
    with pytest.raises(ProviderRateLimitError):
        FutureClient("secret", base_url="https://api.future.test").collect([member()], NOW)

    httpx_mock.add_response(status_code=503)
    with pytest.raises(ProviderTransientError):
        FutureClient("secret", base_url="https://api.future.test").collect([member()], NOW)
