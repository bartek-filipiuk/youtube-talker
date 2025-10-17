"""
Test Configuration and Fixtures

Shared fixtures for all tests.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """
    Fixture for FastAPI TestClient.

    Returns:
        TestClient: Test client for making requests to the API
    """
    return TestClient(app)


@pytest.fixture
def test_env(monkeypatch) -> None:
    """
    Fixture to set test environment variables.

    Args:
        monkeypatch: pytest monkeypatch fixture
    """
    monkeypatch.setenv("ENV", "testing")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:4321,http://localhost:3000")
