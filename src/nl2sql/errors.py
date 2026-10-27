"""Domain errors raised by the agent, the safety layer, and the API."""


class NL2SQLError(Exception):
    """Base error. `code` is a stable identifier for API clients."""

    code = "error"


class UnsafeSQLError(NL2SQLError):
    """The statement is not a single read-only query."""

    code = "unsafe_sql"

    def __init__(self, message: str, reason: str = "forbidden") -> None:
        super().__init__(message)
        self.reason = reason


class InvalidQuestionError(NL2SQLError):
    """The question is blank or longer than the API accepts."""

    code = "invalid_question"


class UnrecognizedQuestionError(NL2SQLError):
    """The offline catalog has no deterministic SQL for this question."""

    code = "unrecognized_question"

    def __init__(self, message: str, sample_questions: list[str]) -> None:
        super().__init__(message)
        self.sample_questions = list(sample_questions)


class QueryTimeoutError(NL2SQLError):
    """SQLite aborted the statement because it exceeded the time budget."""

    code = "query_timeout"


class QueryExecutionError(NL2SQLError):
    """SQLite rejected a statement that had already passed the safety gate."""

    code = "query_execution_error"


class LLMError(NL2SQLError):
    """The optional model call failed or returned a payload we will not run."""

    code = "llm_error"


class ConfigError(NL2SQLError):
    """Environment or settings are inconsistent."""

    code = "config_error"


class WarehouseError(NL2SQLError):
    """The demo database could not be built or read."""

    code = "warehouse_error"
