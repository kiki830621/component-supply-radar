"""Evidence-backed company exposure context that never changes supply scores."""

from __future__ import annotations

from dataclasses import dataclass

from component_supply_radar.models import DirectExposure, ThematicExposure
from component_supply_radar.signals import CategorySignal

RESEARCH_NOTICE = "本內容僅提供供應鏈研究脈絡，不產生投資建議或報酬預測。"


class ExposureRegistry:
    """Keep direct evidence and curated thematic assumptions in separate indexes."""

    def __init__(
        self,
        direct: tuple[DirectExposure, ...],
        thematic: tuple[ThematicExposure, ...],
    ) -> None:
        self._direct = direct
        self._thematic = thematic

    def direct_for_manufacturer(self, manufacturer: str) -> tuple[DirectExposure, ...]:
        key = manufacturer.strip().casefold()
        return tuple(item for item in self._direct if item.manufacturer.casefold() == key)

    def thematic_for_category(self, category: str) -> tuple[ThematicExposure, ...]:
        return tuple(item for item in self._thematic if item.canonical_category == category)


@dataclass(frozen=True, slots=True)
class ExposureContext:
    signal: CategorySignal
    direct: tuple[DirectExposure, ...]
    thematic: tuple[ThematicExposure, ...]
    thematic_is_research_assumption: bool = True
    notice: str = RESEARCH_NOTICE


def attach_exposures(
    signal: CategorySignal,
    registry: ExposureRegistry,
    manufacturers: list[str],
) -> ExposureContext:
    """Attach provenance without calculating or mutating objective pressure."""
    direct: list[DirectExposure] = []
    seen: set[tuple[str, str, str]] = set()
    for manufacturer in manufacturers:
        for item in registry.direct_for_manufacturer(manufacturer):
            identity = (item.manufacturer, item.ticker, item.mapping_version)
            if identity not in seen:
                seen.add(identity)
                direct.append(item)
    return ExposureContext(
        signal=signal,
        direct=tuple(direct),
        thematic=registry.thematic_for_category(signal.canonical_category),
    )
