"""Typed application configuration.

All settings are read from the project-root `.env` file (one level above the
`backend/` directory) or from real environment variables, which take
precedence. Centralising config here keeps secrets out of the code and gives
every module a single, validated source of truth.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/insightforge_mcp/config.py -> repo root is 4 parents up.
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Runtime configuration, validated at startup."""

    database_url: str = "postgresql://postgres:postgres@localhost:5432/insightforge"

    # Query guardrails
    max_query_rows: int = 1000
    query_timeout_ms: int = 10_000

    # Output artifacts (resolved relative to backend/ if not absolute)
    export_dir: str = "exports"

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def export_path(self) -> Path:
        """Absolute path to the export directory, created on demand."""
        p = Path(self.export_dir)
        if not p.is_absolute():
            p = BACKEND_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (read once per process)."""
    return Settings()
