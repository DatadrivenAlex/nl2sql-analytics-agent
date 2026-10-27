"""Shared fixtures. Tests construct Settings explicitly and stay offline."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nl2sql.agent.pipeline import AnalyticsService
from nl2sql.api.app import create_app
from nl2sql.config import Settings
from nl2sql.sql.executor import Executor
from nl2sql.warehouse.seed import build_database


@pytest.fixture(autouse=True)
def _offline_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "NL2SQL_LLM_API_KEY",
        "OPENAI_API_KEY",
        "NL2SQL_LLM_BASE_URL",
        "NL2SQL_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NL2SQL_LLM_MODE", "stub")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "analytics.sqlite"
    build_database(path)
    return path


@pytest.fixture
def settings(db_path: Path) -> Settings:
    return Settings(
        db_path=db_path,
        max_rows=100,
        query_timeout_s=5,
        llm_mode="stub",
        llm_api_key=None,
    )


@pytest.fixture
def service(settings: Settings) -> AnalyticsService:
    return AnalyticsService(settings)


@pytest.fixture
def executor(settings: Settings) -> Executor:
    return Executor(settings.db_path, settings.max_rows, settings.query_timeout_s)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    application = create_app(settings)
    with TestClient(application) as test_client:
        yield test_client
