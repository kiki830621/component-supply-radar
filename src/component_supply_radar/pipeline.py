"""Audited collection orchestration with bounded retry behavior."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Protocol

from component_supply_radar.models import (
    Observation,
    PanelMember,
    RunResult,
    RunStatus,
)
from component_supply_radar.policy import SourcePolicy, require_persistence
from component_supply_radar.providers.future import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransientError,
)

RETRY_DELAYS = (1.0, 2.0)
SECRET_PATTERN = re.compile(r"(?i)\b(api[_ -]?key|token|licensekey)\b\s*[:=]\s*[^\s,;]+")


class CollectionProvider(Protocol):
    source_id: str
    last_request_count: int

    def collect(
        self, members: Sequence[PanelMember], observed_at_utc: datetime
    ) -> tuple[Observation, ...]: ...


class CollectionRepository(Protocol):
    def save_observations(
        self, policy: SourcePolicy, observations: tuple[Observation, ...]
    ) -> None: ...

    def record_run(self, result: RunResult) -> None: ...


def _redact(message: str) -> str:
    return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", message)


class Collector:
    """Run one provider collection without converting failures to zero inventory."""

    def __init__(
        self,
        repository: CollectionRepository,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._sleep = sleep
        self._clock = clock

    def run(
        self,
        provider: CollectionProvider,
        policy: SourcePolicy,
        members: Sequence[PanelMember],
        observed_at_utc: datetime,
    ) -> RunResult:
        """Collect, persist, and audit one source with safe failure semantics."""
        require_persistence(policy)
        if provider.source_id != policy.source_id:
            raise ValueError("provider source_id must match source policy")
        started = self._clock()
        active_count = sum(member.active for member in members)
        try:
            observations = self._collect_with_retry(provider, members, observed_at_utc)
        except (ProviderAuthError, ProviderResponseError) as error:
            return self._failed(provider, policy, started, active_count, error)
        except (ProviderRateLimitError, ProviderTransientError) as error:
            return self._failed(provider, policy, started, active_count, error)

        success_count = len({observation.mpn for observation in observations})
        failure_count = max(active_count - success_count, 0)
        if success_count == 0 and active_count > 0:
            status = RunStatus.FAILED
        elif failure_count:
            status = RunStatus.PARTIAL
        else:
            status = RunStatus.SUCCESS
        self._repository.save_observations(policy, observations)
        result = RunResult(
            source_id=policy.source_id,
            status=status,
            started_at_utc=started,
            completed_at_utc=self._clock(),
            request_count=provider.last_request_count,
            success_count=success_count,
            failure_count=failure_count,
            error_summary=None,
        )
        self._repository.record_run(result)
        return result

    def _collect_with_retry(
        self,
        provider: CollectionProvider,
        members: Sequence[PanelMember],
        observed_at_utc: datetime,
    ) -> tuple[Observation, ...]:
        for attempt in range(3):
            try:
                return provider.collect(members, observed_at_utc)
            except (ProviderRateLimitError, ProviderTransientError):
                if attempt == 2:
                    raise
                self._sleep(RETRY_DELAYS[attempt])
        raise AssertionError("retry loop exhausted without returning or raising")

    def _failed(
        self,
        provider: CollectionProvider,
        policy: SourcePolicy,
        started: datetime,
        failure_count: int,
        error: Exception,
    ) -> RunResult:
        result = RunResult(
            source_id=policy.source_id,
            status=RunStatus.FAILED,
            started_at_utc=started,
            completed_at_utc=self._clock(),
            request_count=provider.last_request_count,
            success_count=0,
            failure_count=failure_count,
            error_summary=_redact(str(error)),
        )
        self._repository.record_run(result)
        return result
