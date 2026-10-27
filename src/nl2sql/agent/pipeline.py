"""Ask flow: ensure the warehouse, generate SQL, execute only the safe form."""

from __future__ import annotations

from nl2sql.agent.llm import OpenAICompatibleGenerator
from nl2sql.agent.stub import SAMPLE_QUESTIONS, StubGenerator
from nl2sql.agent.types import AskAnswer, GeneratedSQL
from nl2sql.config import Settings
from nl2sql.errors import ConfigError, InvalidQuestionError
from nl2sql.sql.executor import Executor
from nl2sql.warehouse.db import introspect, render_ddl
from nl2sql.warehouse.metrics import METRICS
from nl2sql.warehouse.seed import ensure_database


class AnalyticsService:
    """CLI and HTTP share this service so they cannot drift apart."""

    def __init__(self, settings: Settings, generator: object | None = None) -> None:
        self.settings = settings
        self.executor = Executor(
            db_path=settings.db_path,
            max_rows=settings.max_rows,
            timeout_s=settings.query_timeout_s,
        )
        self._generator = generator

    def ensure_ready(self) -> None:
        ensure_database(self.settings.db_path)

    def ping(self) -> None:
        self.ensure_ready()
        result = self.executor.execute("SELECT COUNT(*) AS order_lines FROM fact_order_line")
        if result.row_count != 1:
            raise ConfigError("Warehouse probe did not return a row")

    def schema_document(self) -> dict[str, object]:
        self.ensure_ready()
        snapshot = introspect(self.settings.db_path)
        return {
            "dialect": snapshot["dialect"],
            "objects": snapshot["objects"],
            "metrics": METRICS,
            "sample_questions": list(SAMPLE_QUESTIONS),
            "limits": {
                "max_rows": self.settings.max_rows,
                "query_timeout_s": self.settings.query_timeout_s,
                "generator": "llm" if self.settings.use_live_llm else "stub",
            },
        }

    def ask(self, question: str) -> AskAnswer:
        cleaned = question.strip()
        if not cleaned:
            raise InvalidQuestionError("Question must not be blank")
        if len(cleaned) > 1000:
            raise InvalidQuestionError("Question must be at most 1000 characters")
        self.ensure_ready()
        generated = self._resolve_generator().generate(cleaned)
        if not isinstance(generated, GeneratedSQL):
            raise ConfigError("SQL generator returned an unexpected value")
        result = self.executor.execute(generated.sql)
        return AskAnswer(
            question=cleaned,
            sql=result.sql,
            explanation=generated.explanation,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            truncated=result.truncated,
            source=generated.source,
        )

    def _resolve_generator(self) -> StubGenerator | OpenAICompatibleGenerator:
        if self._generator is not None:
            return self._generator  # type: ignore[return-value]
        ddl = render_ddl(self.settings.db_path)
        self._generator = build_generator(self.settings, ddl)
        return self._generator


def build_generator(settings: Settings, schema_ddl: str) -> StubGenerator | OpenAICompatibleGenerator:
    if not settings.use_live_llm:
        return StubGenerator()
    if not settings.llm_api_key:
        raise ConfigError("NL2SQL_LLM_MODE=live requires NL2SQL_LLM_API_KEY or OPENAI_API_KEY")
    return OpenAICompatibleGenerator(settings, schema_ddl)
