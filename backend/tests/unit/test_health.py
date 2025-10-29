"""
Unit Tests for Health Check Endpoints
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import status
from sqlalchemy.exc import OperationalError

from app.api.routes.health import router
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_basic_health_check():
    """Basic health endpoint should always return ok."""
    response = client.get("/api/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_database_health_check_success():
    """Database health check should return healthy when DB connection succeeds."""
    # Mock database session
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=None)

    # Override dependency
    from app.api.routes.health import health_check_db
    from app.db.session import get_db

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/api/health/db")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy", "service": "postgresql"}

    # Cleanup
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_database_health_check_failure():
    """Database health check should return unhealthy when DB connection fails."""
    # Mock database session to raise exception
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=OperationalError("Connection refused", None, None))

    # Override dependency
    from app.db.session import get_db

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/api/health/db")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["service"] == "postgresql"
    assert "error" in data

    # Cleanup
    app.dependency_overrides.clear()


def test_qdrant_health_check_success():
    """Qdrant health check should return healthy when connection succeeds."""
    # Mock QdrantService instance
    mock_service = MagicMock()
    mock_service.health_check = AsyncMock(return_value=True)

    # Override the get_qdrant_service dependency
    from app.api.routes.health import get_qdrant_service

    def override_get_qdrant_service():
        return mock_service

    app.dependency_overrides[get_qdrant_service] = override_get_qdrant_service

    response = client.get("/api/health/qdrant")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy", "service": "qdrant"}

    # Cleanup
    app.dependency_overrides.clear()


def test_qdrant_health_check_connection_unsuccessful():
    """Qdrant health check should return unhealthy when health_check returns False."""
    # Mock QdrantService instance - health_check returns False
    mock_service = MagicMock()
    mock_service.health_check = AsyncMock(return_value=False)

    # Override the get_qdrant_service dependency
    from app.api.routes.health import get_qdrant_service

    def override_get_qdrant_service():
        return mock_service

    app.dependency_overrides[get_qdrant_service] = override_get_qdrant_service

    response = client.get("/api/health/qdrant")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["service"] == "qdrant"
    assert "error" in data

    # Cleanup
    app.dependency_overrides.clear()


def test_qdrant_health_check_failure():
    """Qdrant health check should return unhealthy when exception is raised."""
    # Mock QdrantService to raise connection error on health_check
    mock_service = MagicMock()
    mock_service.health_check = AsyncMock(side_effect=ConnectionError("Cannot connect to Qdrant"))

    # Override the get_qdrant_service dependency
    from app.api.routes.health import get_qdrant_service

    def override_get_qdrant_service():
        return mock_service

    app.dependency_overrides[get_qdrant_service] = override_get_qdrant_service

    response = client.get("/api/health/qdrant")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["service"] == "qdrant"
    assert "error" in data

    # Cleanup
    app.dependency_overrides.clear()


def test_health_endpoints_exist():
    """Verify all health endpoints are registered."""
    routes = [route.path for route in app.routes]

    assert "/api/health" in routes
    assert "/api/health/db" in routes
    assert "/api/health/qdrant" in routes


def test_basic_health_check_multiple_calls():
    """Basic health check should handle multiple concurrent calls."""
    responses = [client.get("/api/health") for _ in range(10)]

    for response in responses:
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}
