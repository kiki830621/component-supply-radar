from datetime import date

import pytest

from component_supply_radar.config import Settings
from component_supply_radar.policy import (
    PersistenceForbidden,
    SourcePolicy,
    persist_with_policy,
)


def policy(*, persist_allowed: bool) -> SourcePolicy:
    return SourcePolicy(
        source_id="future",
        persist_allowed=persist_allowed,
        cloud_share_allowed=True,
        raw_retention_days=0,
        attribution_required=True,
        terms_reviewed_at=date(2026, 7, 11),
        terms_url="https://www.futureelectronics.com/fr/api-solutions",
    )


def test_source_policy_exposes_six_rights_fields() -> None:
    source_policy = policy(persist_allowed=True)

    assert source_policy.persist_allowed is True
    assert source_policy.cloud_share_allowed is True
    assert source_policy.raw_retention_days == 0
    assert source_policy.attribution_required is True
    assert source_policy.terms_reviewed_at == date(2026, 7, 11)
    assert source_policy.terms_url.startswith("https://")


def test_forbidden_source_never_reaches_sink() -> None:
    writes = 0

    def sink() -> str:
        nonlocal writes
        writes += 1
        return "written"

    with pytest.raises(PersistenceForbidden, match="future"):
        persist_with_policy(policy(persist_allowed=False), sink)

    assert writes == 0


def test_settings_repr_does_not_expose_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUTURE_API_KEY", "future-secret-value")
    monkeypatch.setenv("MOTHERDUCK_TOKEN", "motherduck-secret-value")

    settings = Settings.from_env()

    rendered = repr(settings)
    assert "future-secret-value" not in rendered
    assert "motherduck-secret-value" not in rendered
