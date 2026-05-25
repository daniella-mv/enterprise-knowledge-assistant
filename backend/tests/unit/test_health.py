"""Tests for the /health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["environment"] in {"local", "dev", "prod"}


def test_health_emits_request_id(client: TestClient) -> None:
    response = client.get("/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_chat_endpoint_validates_request_body(client: TestClient) -> None:
    """POST /api/chat with no body fails Pydantic validation."""
    chat = client.post("/api/chat")
    assert chat.status_code == 422
