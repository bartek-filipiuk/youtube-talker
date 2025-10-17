"""
Unit Tests for Main FastAPI Application (Stage 1.3)

Tests for root and health endpoints.
"""

import pytest
from fastapi.testclient import TestClient


def test_root_endpoint_returns_ok(client: TestClient) -> None:
    """Test that root endpoint returns status ok."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "YoutubeTalker API is running"
    assert data["version"] == "0.1.0"
    assert data["docs"] == "/docs"


def test_root_endpoint_response_structure(client: TestClient) -> None:
    """Test that root endpoint returns correct JSON structure."""
    response = client.get("/")
    data = response.json()

    required_fields = ["status", "message", "version", "docs"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"


def test_health_check_endpoint_returns_healthy(client: TestClient) -> None:
    """Test that health check endpoint returns healthy status."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "youtube-talker-api"
    assert "environment" in data


def test_health_check_includes_environment(client: TestClient) -> None:
    """Test that health check includes environment variable."""
    response = client.get("/health")
    data = response.json()

    assert "environment" in data
    # Environment should be one of: development, testing, production
    assert data["environment"] in ["development", "testing", "production"]


def test_swagger_docs_accessible(client: TestClient) -> None:
    """Test that Swagger UI documentation is accessible."""
    response = client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_redoc_accessible(client: TestClient) -> None:
    """Test that ReDoc documentation is accessible."""
    response = client.get("/redoc")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_json_accessible(client: TestClient) -> None:
    """Test that OpenAPI JSON schema is accessible."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert data["info"]["title"] == "YoutubeTalker API"
    assert data["info"]["version"] == "0.1.0"


def test_nonexistent_endpoint_returns_404(client: TestClient) -> None:
    """Test that accessing non-existent endpoint returns 404."""
    response = client.get("/nonexistent")

    assert response.status_code == 404
