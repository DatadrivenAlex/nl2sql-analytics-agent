"""Mode selection stays offline unless a key is actually configured."""

from __future__ import annotations

from pathlib import Path

import pytest

from nl2sql.config import Settings
from nl2sql.errors import ConfigError


def test_stub_mode_ignores_a_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NL2SQL_LLM_MODE", "stub")
    monkeypatch.setenv("NL2SQL_LLM_API_KEY", "present")
    monkeypatch.setenv("NL2SQL_DB_PATH", str(tmp_path / "warehouse.sqlite"))
    settings = Settings.from_env()
    assert settings.llm_api_key == "present"
    assert settings.use_live_llm is False


def test_auto_uses_openai_key_when_dedicated_key_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NL2SQL_LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("NL2SQL_LLM_MODE", "auto")
    settings = Settings.from_env()
    assert settings.llm_api_key == "sk-test"
    assert settings.use_live_llm is True


def test_dedicated_key_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NL2SQL_LLM_API_KEY", "dedicated")
    monkeypatch.setenv("OPENAI_API_KEY", "fallback")
    monkeypatch.setenv("NL2SQL_LLM_MODE", "auto")
    assert Settings.from_env().llm_api_key == "dedicated"


def test_rejects_key_inside_the_base_url() -> None:
    with pytest.raises(ConfigError):
        Settings(
            llm_mode="live",
            llm_api_key="test-key",
            llm_base_url="https://user:secret@models.example/v1",
        )


def test_rejects_excessive_row_cap() -> None:
    with pytest.raises(ConfigError):
        Settings(max_rows=10_000)
