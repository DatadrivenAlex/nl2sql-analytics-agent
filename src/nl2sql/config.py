"""Runtime settings. The default path never requires an API key."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from nl2sql.errors import ConfigError

MAX_ROWS_CEILING = 1000
LLM_MODES = ("auto", "stub", "live")


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True)
class Settings:
    """Process configuration.

    `llm_mode="auto"` uses the live model only when an API key is present.
    `stub` stays offline even if a key happens to be in the environment.
    """

    db_path: Path = Path("data/analytics.sqlite")
    max_rows: int = 100
    query_timeout_s: float = 5.0
    llm_mode: str = "auto"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_s: float = 30.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "db_path", Path(self.db_path))
        mode = self.llm_mode.strip().lower()
        if mode not in LLM_MODES:
            raise ConfigError("NL2SQL_LLM_MODE must be one of: auto, stub, live")
        object.__setattr__(self, "llm_mode", mode)
        object.__setattr__(self, "llm_api_key", _blank_to_none(self.llm_api_key))
        if not 1 <= self.max_rows <= MAX_ROWS_CEILING:
            raise ConfigError(f"NL2SQL_MAX_ROWS must be between 1 and {MAX_ROWS_CEILING}")
        if not 0 < self.query_timeout_s <= 60:
            raise ConfigError("NL2SQL_QUERY_TIMEOUT_S must be greater than 0 and at most 60")
        if not 0 < self.llm_timeout_s <= 120:
            raise ConfigError("NL2SQL_LLM_TIMEOUT_S must be greater than 0 and at most 120")
        if self.use_live_llm:
            _validate_base_url(self.llm_base_url)

    @property
    def use_live_llm(self) -> bool:
        if self.llm_mode == "stub":
            return False
        if self.llm_mode == "live":
            return True
        return self.llm_api_key is not None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            db_path=Path(os.environ.get("NL2SQL_DB_PATH", "data/analytics.sqlite")),
            max_rows=_env_int("NL2SQL_MAX_ROWS", 100),
            query_timeout_s=_env_float("NL2SQL_QUERY_TIMEOUT_S", 5.0),
            llm_mode=os.environ.get("NL2SQL_LLM_MODE", "auto"),
            llm_api_key=_blank_to_none(
                os.environ.get("NL2SQL_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
            ),
            llm_base_url=os.environ.get("NL2SQL_LLM_BASE_URL", "https://api.openai.com/v1"),
            llm_model=os.environ.get("NL2SQL_LLM_MODEL", "gpt-4o-mini"),
            llm_timeout_s=_env_float("NL2SQL_LLM_TIMEOUT_S", 30.0),
        )


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc


def _validate_base_url(base_url: str) -> None:
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError("NL2SQL_LLM_BASE_URL must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ConfigError("Put the model credential in NL2SQL_LLM_API_KEY, not in the URL")
