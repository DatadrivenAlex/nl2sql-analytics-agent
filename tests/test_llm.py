"""The optional model client parses JSON and cannot bypass the safety gate."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from nl2sql.agent.llm import parse_model_payload
from nl2sql.agent.pipeline import AnalyticsService
from nl2sql.config import Settings
from nl2sql.errors import LLMError, UnsafeSQLError


def test_parse_fenced_json() -> None:
    generated = parse_model_payload(
        'Sure\n```json\n{"sql": "SELECT 1 AS n", "explanation": "probe"}\n```'
    )
    assert generated.sql == "SELECT 1 AS n"
    assert generated.explanation == "probe"
    assert generated.source == "llm"


def test_parse_rejects_non_json() -> None:
    with pytest.raises(LLMError):
        parse_model_payload("just do a SELECT")


def test_live_call_uses_schema_and_executes_safe_sql(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content.decode())
        system = body["messages"][0]["content"]
        assert "fact_order_line" in system
        assert "net_amount_cents" in system
        assert body["messages"][1]["content"] == "How many customers do we have?"
        content = json.dumps(
            {
                "sql": "SELECT COUNT(*) AS customers FROM dim_customer",
                "explanation": "Counts every customer row.",
            }
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    _patch_client(monkeypatch, handler)
    settings = Settings(
        db_path=db_path,
        llm_mode="live",
        llm_api_key="test-key",
        llm_base_url="https://models.example/v1",
        llm_model="demo",
    )
    answer = AnalyticsService(settings).ask("How many customers do we have?")
    assert answer.source == "llm"
    assert answer.rows == [{"customers": 12}]
    assert "customer" in answer.sql.lower()


def test_live_model_cannot_drop_a_table(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        content = json.dumps({"sql": "DROP TABLE dim_customer; SELECT 1", "explanation": "no"})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    _patch_client(monkeypatch, handler)
    settings = Settings(
        db_path=db_path,
        llm_mode="live",
        llm_api_key="test-key",
        llm_base_url="https://models.example/v1",
    )
    with pytest.raises(UnsafeSQLError):
        AnalyticsService(settings).ask("please delete the customers")
    import sqlite3

    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0] == 12
    finally:
        connection.close()


def test_redirects_are_not_followed(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(302, headers={"location": "https://evil.example/steal"})

    _patch_client(monkeypatch, handler)
    settings = Settings(
        db_path=db_path,
        llm_mode="auto",
        llm_api_key="test-key",
        llm_base_url="https://models.example/v1",
    )
    with pytest.raises(LLMError):
        AnalyticsService(settings).ask("What were total net sales by region in 2025?")


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_client = httpx.Client

    def factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("nl2sql.agent.llm.httpx.Client", factory)
