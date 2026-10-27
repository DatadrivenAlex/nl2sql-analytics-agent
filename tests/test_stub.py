"""Offline catalog: known questions resolve, everything else fails closed."""

from __future__ import annotations

from pathlib import Path

import pytest

from nl2sql.agent.stub import SAMPLE_QUESTIONS, match_question, normalize_question
from nl2sql.errors import UnrecognizedQuestionError


def test_hiring_manager_questions_are_first() -> None:
    assert SAMPLE_QUESTIONS[:3] == (
        "What were total net sales by region in 2025?",
        "Which product category generated the most revenue?",
        "How many orders did Enterprise customers place?",
    )


def test_case_and_punctuation_do_not_matter() -> None:
    left = match_question("WHAT WERE TOTAL NET SALES BY REGION IN 2025?")
    right = match_question("  show net sales by region in 2025 please  ")
    assert left.sql == right.sql
    assert left.source == "stub"
    assert "completed" in left.explanation.lower()


def test_category_alias() -> None:
    generated = match_question("top product category by revenue")
    assert "dim_product" in generated.sql
    assert "completed" in generated.sql


def test_enterprise_alias_mentions_grain() -> None:
    generated = match_question("How many orders were placed by Enterprise customers?")
    assert "COUNT(DISTINCT" in generated.sql.upper() or "count(distinct" in generated.sql.lower()
    assert "order line" in generated.explanation.lower()


@pytest.mark.parametrize("question", SAMPLE_QUESTIONS)
def test_every_catalog_question_normalizes_to_itself(question: str) -> None:
    assert normalize_question(question)
    assert match_question(question).sql.strip()


def test_unknown_question_does_not_invent_sql() -> None:
    with pytest.raises(UnrecognizedQuestionError) as caught:
        match_question("What is the meaning of life?")
    assert caught.value.sample_questions[:3] == list(SAMPLE_QUESTIONS[:3])


def test_readme_lists_the_three_sample_questions() -> None:
    readme = Path(__file__).resolve().parents[1].joinpath("README.md").read_text(encoding="utf-8")
    for question in SAMPLE_QUESTIONS[:3]:
        assert question in readme


def test_schema_doc_states_the_metric_and_grain() -> None:
    document = Path(__file__).resolve().parents[1].joinpath("docs", "schema.md").read_text(encoding="utf-8")
    assert "fact_order_line" in document
    assert "net_amount_cents" in document
    assert "completed" in document
    assert "order line" in document.lower()
