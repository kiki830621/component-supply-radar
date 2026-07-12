"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _optional_secret(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated runtime settings with secrets hidden from object representations."""

    database_path: Path
    timezone: str
    motherduck_database: str
    future_api_key: str | None = field(default=None, repr=False)
    motherduck_token: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> Settings:
        """Load settings from an ignored local environment file and process environment."""
        load_dotenv()
        database = Path(os.getenv("RADAR_DATABASE", "data/radar.duckdb")).expanduser()
        if not database.is_absolute():
            database = Path.cwd() / database
        motherduck_database = os.getenv("MOTHERDUCK_DATABASE", "component_supply_radar").strip()
        if not motherduck_database:
            raise ValueError("MOTHERDUCK_DATABASE must not be empty")
        timezone = os.getenv("RADAR_TIMEZONE", "Asia/Taipei").strip()
        if not timezone:
            raise ValueError("RADAR_TIMEZONE must not be empty")
        return cls(
            database_path=database,
            timezone=timezone,
            motherduck_database=motherduck_database,
            future_api_key=_optional_secret("FUTURE_API_KEY"),
            motherduck_token=_optional_secret("MOTHERDUCK_TOKEN"),
        )
