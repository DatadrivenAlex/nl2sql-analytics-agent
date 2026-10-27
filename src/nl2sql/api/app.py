"""FastAPI application: ask, schema, health, and readiness."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from nl2sql import __version__
from nl2sql.agent.pipeline import AnalyticsService
from nl2sql.config import Settings
from nl2sql.errors import (
    ConfigError,
    InvalidQuestionError,
    LLMError,
    NL2SQLError,
    QueryExecutionError,
    QueryTimeoutError,
    UnrecognizedQuestionError,
    UnsafeSQLError,
    WarehouseError,
)

router = APIRouter()

_STATUS = {
    InvalidQuestionError: 422,
    UnrecognizedQuestionError: 400,
    UnsafeSQLError: 400,
    QueryExecutionError: 400,
    QueryTimeoutError: 408,
    LLMError: 502,
    ConfigError: 500,
    WarehouseError: 503,
}


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class AskResponse(BaseModel):
    question: str
    sql: str
    explanation: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    source: str


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/ready", response_model=None)
def ready(request: Request) -> dict[str, str] | JSONResponse:
    service: AnalyticsService = request.app.state.service
    try:
        service.ping()
    except NL2SQLError as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "detail": str(exc)},
        )
    return {"status": "ready", "dialect": "sqlite"}


@router.get("/v1/schema")
def schema(request: Request) -> dict[str, Any]:
    service: AnalyticsService = request.app.state.service
    return service.schema_document()


@router.post("/v1/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request) -> AskResponse:
    service: AnalyticsService = request.app.state.service
    answer = service.ask(body.question)
    return AskResponse(**answer.as_dict())


def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    del request
    if not isinstance(exc, NL2SQLError):
        raise exc
    payload: dict[str, Any] = {"code": exc.code, "message": str(exc)}
    if isinstance(exc, UnsafeSQLError):
        payload["reason"] = exc.reason
    if isinstance(exc, UnrecognizedQuestionError):
        payload["sample_questions"] = exc.sample_questions
    status = _STATUS.get(type(exc), 400)
    return JSONResponse(status_code=status, content={"detail": payload})


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.service.ensure_ready()
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings if settings is not None else Settings.from_env()
    app = FastAPI(
        title="NL2SQL Analytics Agent",
        version=__version__,
        summary="Natural-language questions over a small demo analytics warehouse.",
        lifespan=_lifespan,
    )
    app.state.service = AnalyticsService(active)
    app.include_router(router)
    app.add_exception_handler(NL2SQLError, _handle_domain_error)
    return app


_app: FastAPI | None = None


def __getattr__(name: str) -> FastAPI:
    """Build the process-wide app on first use so imports stay side-effect free."""
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
