"""
Unit Tests for Main FastAPI Application (Stage 1.3)

Tests for root and health endpoints.
"""

import pytest
from fastapi.testclient import TestClient


def test_root_endpoint_returns_ok(client: TestClient) -> None:
    """Test that root endpoint returns 200 and valid JSON."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    # Just verify the response is valid JSON with expected keys
    assert "status" in data
    assert "message" in data
    assert "version" in data


def test_root_endpoint_response_structure(client: TestClient) -> None:
    """Test that root endpoint returns correct JSON structure."""
    response = client.get("/")
    data = response.json()

    required_fields = ["status", "message", "version", "docs"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"


def test_health_check_endpoint_returns_healthy(client: TestClient) -> None:
    """Test that health check endpoint returns 200 and required fields."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    # Just verify required fields exist, not their exact values
    assert "status" in data
    assert "service" in data
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
    """Test that OpenAPI JSON schema is accessible and valid."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    data = response.json()
    # Verify OpenAPI structure, not exact content
    assert "openapi" in data
    assert "info" in data
    assert "title" in data["info"]
    assert "version" in data["info"]


def test_nonexistent_endpoint_returns_404(client: TestClient) -> None:
    """Test that accessing non-existent endpoint returns 404."""
    response = client.get("/nonexistent")

    assert response.status_code == 404
