"""Optional OpenAI-compatible chat client. Unused when no API key is configured."""

from __future__ import annotations

import json
import re

import httpx

from nl2sql.agent.prompt import build_system_prompt
from nl2sql.agent.types import GeneratedSQL
from nl2sql.config import Settings
from nl2sql.errors import ConfigError, LLMError

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class OpenAICompatibleGenerator:
    """One chat completion. The SQL it returns still has to pass the safety gate."""

    def __init__(self, settings: Settings, schema_ddl: str) -> None:
        if not settings.llm_api_key:
            raise ConfigError(
                "A live model requires NL2SQL_LLM_API_KEY or OPENAI_API_KEY"
            )
        self._settings = settings
        self._system_prompt = build_system_prompt(schema_ddl, settings.max_rows)

    def generate(self, question: str) -> GeneratedSQL:
        payload = {
            "model": self._settings.llm_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": question},
            ],
        }
        url = self._settings.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(
                timeout=self._settings.llm_timeout_s,
                follow_redirects=False,
            ) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LLMError("Could not reach the configured model endpoint") from exc
        if response.status_code >= 400:
            detail = response.text[:300].replace("\n", " ")
            raise LLMError(f"The model endpoint returned HTTP {response.status_code}: {detail}")
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("The model endpoint returned an unexpected payload") from exc
        if not isinstance(content, str):
            raise LLMError("The model endpoint returned an unexpected payload")
        return parse_model_payload(content)


def parse_model_payload(content: str) -> GeneratedSQL:
    """Accept raw JSON or a single fenced JSON object. Ignore anything else."""
    text = content.strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError("Model response was not JSON with a sql field") from exc
    if not isinstance(data, dict):
        raise LLMError("Model response was not JSON with a sql field")
    sql = data.get("sql")
    explanation = data.get("explanation", "")
    if not isinstance(sql, str) or not sql.strip():
        raise LLMError("Model response was not JSON with a sql field")
    if not isinstance(explanation, str):
        raise LLMError("Model explanation must be a string")
    return GeneratedSQL(sql=sql.strip(), explanation=explanation.strip(), source="llm")
