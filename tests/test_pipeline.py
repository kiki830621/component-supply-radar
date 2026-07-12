from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from component_supply_radar.models import (
    Observation,
    PanelMember,
    PanelRole,
    PriceBreak,
    RunResult,
    RunStatus,
)
from component_supply_radar.pipeline import Collector
from component_supply_radar.policy import PersistenceForbidden, SourcePolicy
from component_supply_radar.providers.future import (
    ProviderAuthError,
    ProviderRateLimitError,
)

NOW = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)


def source_policy(*, allowed: bool = True) -> SourcePolicy:
    return SourcePolicy(
        "future",
        allowed,
        True,
        0,
        True,
        date(2026, 7, 11),
        "https://www.futureelectronics.com/fr/api-solutions",
    )


def panel_member() -> PanelMember:
    return PanelMember(
        "BAT54STA",
        "onsemi",
        "Schottky Diodes",
        "power-semiconductor",
        "2026-v1",
        "2026-Q3",
        PanelRole.CORE,
        True,
    )


def observation() -> Observation:
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
        (PriceBreak(100, None, Decimal("0.218"), "USD"),),
        None,
        "a" * 64,
    )


class FakeProvider:
    source_id = "future"

    def __init__(self, failures: list[Exception] | None = None) -> None:
        self.failures = list(failures or [])
        self.calls = 0
        self.last_request_count = 0

    def collect(
        self, members: list[PanelMember], observed_at_utc: datetime
    ) -> tuple[Observation, ...]:
        self.calls += 1
        self.last_request_count += 1
        if self.failures:
            raise self.failures.pop(0)
        return (observation(),)


class FakeRepository:
    def __init__(self) -> None:
        self.saved: list[Observation] = []
        self.runs: list[RunResult] = []

    def save_observations(
        self, policy: SourcePolicy, observations: tuple[Observation, ...]
    ) -> None:
        self.saved.extend(observations)

    def record_run(self, result: RunResult) -> None:
        self.runs.append(result)


def test_transient_failure_retries_and_saves_once() -> None:
    provider = FakeProvider([ProviderRateLimitError("slow down")])
    repository = FakeRepository()
    delays: list[float] = []

    result = Collector(repository, sleep=delays.append).run(
        provider, source_policy(), [panel_member()], NOW
    )

    assert result.status is RunStatus.SUCCESS
    assert provider.calls == 2
    assert delays == [1.0]
    assert repository.saved == [observation()]
    assert repository.runs == [result]


def test_auth_failure_is_not_retried_or_saved_as_zero() -> None:
    provider = FakeProvider([ProviderAuthError("api_key=supersecret rejected")])
    repository = FakeRepository()

    result = Collector(repository, sleep=lambda _: None).run(
        provider, source_policy(), [panel_member()], NOW
    )

    assert result.status is RunStatus.FAILED
    assert provider.calls == 1
    assert repository.saved == []
    assert result.error_summary is not None
    assert "supersecret" not in result.error_summary


def test_forbidden_policy_stops_before_provider_network_call() -> None:
    provider = FakeProvider()
    repository = FakeRepository()

    with pytest.raises(PersistenceForbidden):
        Collector(repository, sleep=lambda _: None).run(
            provider, source_policy(allowed=False), [panel_member()], NOW
        )

    assert provider.calls == 0
    assert repository.saved == []
