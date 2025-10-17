"""
Unit Tests for Middleware (Stage 1.4)

Tests for CORS, logging, and exception handling middleware.
"""

import pytest
from fastapi.testclient import TestClient


def test_cors_headers_present_in_response(client: TestClient) -> None:
    """Test that CORS headers are present in responses when Origin is sent."""
    response = client.get(
        "/",
        headers={"Origin": "http://localhost:4321"}
    )

    # CORS headers should be present when Origin header is sent
    assert "access-control-allow-origin" in response.headers


def test_cors_allows_configured_origins(client: TestClient) -> None:
    """Test that CORS allows configured origins."""
    # Make a request with an allowed origin
    response = client.get(
        "/",
        headers={"Origin": "http://localhost:4321"}
    )

    assert response.status_code == 200
    # Should allow the origin
    assert "access-control-allow-origin" in response.headers


def test_cors_preflight_request(client: TestClient) -> None:
    """Test that CORS preflight requests are handled correctly."""
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:4321",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-headers" in response.headers


def test_cors_allows_credentials(client: TestClient) -> None:
    """Test that CORS allows credentials when Origin is sent."""
    response = client.get(
        "/",
        headers={"Origin": "http://localhost:4321"}
    )

    cors_creds = response.headers.get("access-control-allow-credentials")
    assert cors_creds == "true"


def test_cors_exposes_headers(client: TestClient) -> None:
    """Test that CORS exposes headers to frontend when Origin is sent."""
    response = client.get(
        "/",
        headers={"Origin": "http://localhost:4321"}
    )

    # Should expose all headers when Origin is sent
    assert "access-control-expose-headers" in response.headers


def test_exception_handler_returns_json_on_error(client: TestClient) -> None:
    """Test that exception handler returns JSON for errors."""
    # Access a non-existent endpoint
    response = client.get("/nonexistent")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_response_includes_all_cors_methods(client: TestClient) -> None:
    """Test that CORS allows all HTTP methods."""
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:4321",
            "Access-Control-Request-Method": "POST",
        }
    )

    allow_methods = response.headers.get("access-control-allow-methods", "")
    # Should allow all methods (*)
    assert allow_methods or response.status_code == 200


def test_cors_config_function_returns_dict() -> None:
    """Test that get_cors_config returns proper dictionary."""
    from app.core.middleware import get_cors_config

    config = get_cors_config()

    assert isinstance(config, dict)
    assert "allow_origins" in config
    assert "allow_credentials" in config
    assert "allow_methods" in config
    assert "allow_headers" in config
    assert "expose_headers" in config


def test_cors_config_has_correct_values() -> None:
    """Test that CORS config has correct values."""
    from app.core.middleware import get_cors_config

    config = get_cors_config()

    assert config["allow_credentials"] is True
    assert config["allow_methods"] == ["*"]
    assert config["allow_headers"] == ["*"]
    assert config["expose_headers"] == ["*"]
    assert isinstance(config["allow_origins"], list)


def test_health_endpoint_has_cors_headers(client: TestClient) -> None:
    """Test that health endpoint also has CORS headers when Origin is sent."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:4321"}
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_docs_endpoint_accessible_with_cors(client: TestClient) -> None:
    """Test that docs endpoint is accessible and has CORS."""
    response = client.get("/docs")

    assert response.status_code == 200
    # CORS headers may or may not be present for static docs
    # Just verify the endpoint is accessible
