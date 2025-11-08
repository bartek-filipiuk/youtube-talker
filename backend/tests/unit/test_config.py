"""
Unit Tests for Configuration (Stage 1.3)

Tests for settings loading and validation.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_loads_with_defaults() -> None:
    """Test that settings can be loaded with default values."""
    settings = Settings()

    assert settings.ENV == "development"
    assert settings.DEBUG is True
    assert isinstance(settings.DATABASE_URL, str)
    assert isinstance(settings.QDRANT_URL, str)


def test_settings_loads_from_env(monkeypatch) -> None:
    """Test that settings can be loaded from environment variables."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")

    settings = Settings()

    assert settings.ENV == "production"
    assert settings.DEBUG is False
    assert settings.DATABASE_URL == "postgresql://test:test@localhost/test"


def test_allowed_origins_list_parsing() -> None:
    """Test that ALLOWED_ORIGINS is correctly parsed into a list."""
    settings = Settings()

    origins = settings.allowed_origins_list
    assert isinstance(origins, list)
    assert len(origins) > 0
    assert all(isinstance(origin, str) for origin in origins)


def test_allowed_origins_list_with_custom_origins(monkeypatch) -> None:
    """Test ALLOWED_ORIGINS parsing with custom values."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://example.com,http://test.com,http://localhost:3000")

    settings = Settings()
    origins = settings.allowed_origins_list

    assert len(origins) == 3
    assert "http://example.com" in origins
    assert "http://test.com" in origins
    assert "http://localhost:3000" in origins


def test_allowed_origins_handles_whitespace(monkeypatch) -> None:
    """Test that ALLOWED_ORIGINS parsing handles whitespace correctly."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://example.com , http://test.com , http://localhost:3000")

    settings = Settings()
    origins = settings.allowed_origins_list

    # Should strip whitespace
    assert "http://example.com" in origins
    assert "http://test.com" in origins
    assert "http://localhost:3000" in origins


def test_rag_configuration_defaults() -> None:
    """Test RAG configuration default values."""
    settings = Settings()

    assert settings.RAG_TOP_K == 12
    assert settings.RAG_CONTEXT_MESSAGES == 10
    assert settings.CHUNK_SIZE == 700
    assert settings.CHUNK_OVERLAP_PERCENT == 20


def test_session_expires_days_default() -> None:
    """Test session expiry configuration."""
    settings = Settings()

    assert settings.SESSION_EXPIRES_DAYS == 7
    assert isinstance(settings.SESSION_EXPIRES_DAYS, int)


def test_openrouter_model_defaults() -> None:
    """Test OpenRouter and OpenAI model configuration defaults."""
    settings = Settings()

    # OpenRouter models (dual LLM strategy)
    assert settings.OPENROUTER_CLAUDE_MODEL == "anthropic/claude-haiku-4.5"
    assert settings.OPENROUTER_GEMINI_MODEL == "google/gemini-2.5-flash"

    # OpenAI for embeddings
    assert settings.OPENAI_EMBEDDING_MODEL == "text-embedding-3-small"


def test_database_url_format() -> None:
    """Test that DATABASE_URL is in correct format."""
    settings = Settings()

    assert settings.DATABASE_URL.startswith("postgresql")
    assert "youtube" in settings.DATABASE_URL.lower()


def test_qdrant_url_format() -> None:
    """Test that QDRANT_URL is in correct format."""
    settings = Settings()

    assert settings.QDRANT_URL.startswith("http")
    assert "localhost" in settings.QDRANT_URL or "qdrant" in settings.QDRANT_URL
