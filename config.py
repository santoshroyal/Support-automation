"""Top-level configuration loaded from environment.

Pure environment-driven settings (database connection, runtime paths). All
other configurable values — stakeholders, thresholds, source modes, prompt
templates — live in YAML files under `config_files/` and `prompts/`,
edited by engineers via pull request. Users of the dashboard cannot edit
configuration; that's by design.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SUPPORT_AUTOMATION_", env_file=".env", extra="ignore")

    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parent)

    # Database
    # Set this env var to switch the system from in-memory to Postgres.
    # Example: SUPPORT_AUTOMATION_DATABASE_URL=postgresql+psycopg://support_automation@localhost/support_automation_local
    database_url: str | None = None
    database_pool_size: int = 25
    database_pool_max_overflow: int = 5
    database_statement_timeout_ms: int = 5_000
    database_idle_in_tx_timeout_ms: int = 30_000

    # Filesystem layout
    data_fixtures_dir: Path = Field(default=Path("data_fixtures"))
    secrets_dir: Path = Field(default=Path("secrets"))
    drafts_output_dir: Path = Field(default=Path("var/support_automation/drafts"))
    digests_output_dir: Path = Field(default=Path("var/log/digests"))

    log_level: str = "INFO"

    def absolute(self, relative: Path | str) -> Path:
        path = Path(relative)
        return path if path.is_absolute() else (self.project_root / path).resolve()

    def use_postgres(self) -> bool:
        return self.database_url is not None and self.database_url.strip() != ""


_config: AppConfig | None = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reset_config_for_tests() -> None:
    """Drops the cached settings. Tests use this when they swap env vars."""
    global _config
    _config = None
