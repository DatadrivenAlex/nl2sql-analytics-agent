"""HTTP surface for the three sample questions and the safety failures."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_ready(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_schema_lists_the_fact_table(client: TestClient) -> None:
    response = client.get("/v1/schema")
    assert response.status_code == 200
    body = response.json()
    names = {item["name"] for item in body["objects"]}
    assert "fact_order_line" in names
    assert body["sample_questions"][0].startswith("What were total net sales")
    metric_names = {metric["name"] for metric in body["metrics"]}
    assert "net_sales" in metric_names


def test_ask_region_question(client: TestClient) -> None:
    response = client.post(
        "/v1/ask",
        json={"question": "What were total net sales by region in 2025?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "stub"
    assert body["columns"][0] == "region"
    assert body["row_count"] == len(body["rows"])
    assert body["rows"][0]["region"] == "North"
    assert "select" in body["sql"].lower()
    assert body["explanation"]


def test_ask_category_and_enterprise(client: TestClient) -> None:
    category = client.post(
        "/v1/ask",
        json={"question": "Which product category generated the most revenue?"},
    )
    enterprise = client.post(
        "/v1/ask",
        json={"question": "How many orders did Enterprise customers place?"},
    )
    assert category.status_code == 200
    assert enterprise.status_code == 200
    assert category.json()["rows"][0]["category"]
    assert enterprise.json()["rows"][0]["orders"] < enterprise.json()["rows"][0]["order_lines"]


def test_unknown_question_returns_samples(client: TestClient) -> None:
    response = client.post("/v1/ask", json={"question": "DROP TABLE fact_order_line"})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "unrecognized_question"
    assert any("region" in question for question in detail["sample_questions"])
    still_there = client.post(
        "/v1/ask",
        json={"question": "How many products are in each category?"},
    )
    assert still_there.status_code == 200
    assert sum(row["products"] for row in still_there.json()["rows"]) == 10


def test_blank_question_is_422(client: TestClient) -> None:
    response = client.post("/v1/ask", json={"question": "   "})
    assert response.status_code == 422


def test_missing_question_is_422(client: TestClient) -> None:
    response = client.post("/v1/ask", json={})
    assert response.status_code == 422
