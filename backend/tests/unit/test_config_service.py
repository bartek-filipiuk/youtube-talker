"""
Unit Tests for Config Service
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.config_service import ConfigService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def config_service(mock_db):
    """Create a ConfigService instance with mocked database."""
    return ConfigService(mock_db)


# get_config Tests

@pytest.mark.asyncio
async def test_get_config_loads_cache_on_first_access(config_service, mock_db):
    """Should load cache from database on first get_config call."""
    # Mock repository
    mock_config_item = MagicMock()
    mock_config_item.key = "test.key"
    mock_config_item.value = {"value": "123", "type": "int"}

    with patch('app.services.config_service.ConfigRepository') as mock_repo_class:
        mock_repo = MagicMock()
        mock_repo.get_all = AsyncMock(return_value=[mock_config_item])
        mock_repo_class.return_value = mock_repo

        # First call should load cache
        result = await config_service.get_config("test.key")

        assert result == 123
        assert config_service._cache_loaded is True
        mock_repo.get_all.assert_called_once()


@pytest.mark.asyncio
async def test_get_config_uses_cache_on_subsequent_calls(config_service):
    """Should use cache without database access on subsequent calls."""
    # Manually populate cache
    config_service._cache = {"test.key": 456}
    config_service._cache_loaded = True

    # Mock repository (should not be called)
    with patch('app.services.config_service.ConfigRepository') as mock_repo_class:
        mock_repo = MagicMock()
        mock_repo.get_all = AsyncMock()
        mock_repo_class.return_value = mock_repo

        result = await config_service.get_config("test.key")

        assert result == 456
        # Repository should not be called (cache already loaded)
        mock_repo.get_all.assert_not_called()


@pytest.mark.asyncio
async def test_get_config_returns_default_when_key_not_found(config_service):
    """Should return default value when key doesn't exist."""
    # Set cache as loaded with empty data
    config_service._cache = {}
    config_service._cache_loaded = True

    result = await config_service.get_config("nonexistent.key", default=999)

    assert result == 999


@pytest.mark.asyncio
async def test_get_config_returns_none_when_no_default(config_service):
    """Should return None when key not found and no default provided."""
    config_service._cache = {}
    config_service._cache_loaded = True

    result = await config_service.get_config("nonexistent.key")

    assert result is None


# Type Parsing Tests

def test_parse_value_int(config_service):
    """Should parse string to int."""
    assert config_service._parse_value("42", "int") == 42
    assert config_service._parse_value("0", "int") == 0
    assert config_service._parse_value("-10", "int") == -10


def test_parse_value_float(config_service):
    """Should parse string to float."""
    assert config_service._parse_value("3.14", "float") == 3.14
    assert config_service._parse_value("0.0", "float") == 0.0
    assert config_service._parse_value("-1.5", "float") == -1.5


def test_parse_value_bool_true(config_service):
    """Should parse various true values to boolean True."""
    assert config_service._parse_value("true", "bool") is True
    assert config_service._parse_value("True", "bool") is True
    assert config_service._parse_value("TRUE", "bool") is True
    assert config_service._parse_value("1", "bool") is True
    assert config_service._parse_value("yes", "bool") is True
    assert config_service._parse_value("YES", "bool") is True


def test_parse_value_bool_false(config_service):
    """Should parse various false values to boolean False."""
    assert config_service._parse_value("false", "bool") is False
    assert config_service._parse_value("False", "bool") is False
    assert config_service._parse_value("FALSE", "bool") is False
    assert config_service._parse_value("0", "bool") is False
    assert config_service._parse_value("no", "bool") is False
    assert config_service._parse_value("anything", "bool") is False


def test_parse_value_str(config_service):
    """Should return string unchanged."""
    assert config_service._parse_value("hello", "str") == "hello"
    assert config_service._parse_value("123", "str") == "123"
    assert config_service._parse_value("", "str") == ""


# refresh Tests

@pytest.mark.asyncio
async def test_refresh_clears_and_reloads_cache(config_service, mock_db):
    """Should clear cache and reload from database."""
    # Populate initial cache
    config_service._cache = {"old.key": "old_value"}
    config_service._cache_loaded = True

    # Mock repository with new data
    mock_config_item = MagicMock()
    mock_config_item.key = "new.key"
    mock_config_item.value = {"value": "new_value", "type": "str"}

    with patch('app.services.config_service.ConfigRepository') as mock_repo_class:
        mock_repo = MagicMock()
        mock_repo.get_all = AsyncMock(return_value=[mock_config_item])
        mock_repo_class.return_value = mock_repo

        await config_service.refresh()

        # Old key should be gone, new key should be present
        assert "old.key" not in config_service._cache
        assert config_service._cache["new.key"] == "new_value"
        mock_repo.get_all.assert_called_once()


# get_cached_value Tests

def test_get_cached_value_returns_cached_value(config_service):
    """Should return value from cache without loading."""
    config_service._cache = {"test.key": 789}

    result = config_service.get_cached_value("test.key")

    assert result == 789


def test_get_cached_value_returns_none_when_not_found(config_service):
    """Should return None when key not in cache."""
    config_service._cache = {}

    result = config_service.get_cached_value("nonexistent.key")

    assert result is None


def test_get_cached_value_returns_none_when_cache_not_loaded(config_service):
    """Should return None when cache not yet loaded."""
    # Cache not loaded
    config_service._cache_loaded = False

    result = config_service.get_cached_value("any.key")

    assert result is None


# _load_cache Tests

@pytest.mark.asyncio
async def test_load_cache_handles_multiple_items(config_service, mock_db):
    """Should load multiple config items with different types."""
    mock_items = [
        MagicMock(key="int.key", value={"value": "10", "type": "int"}),
        MagicMock(key="float.key", value={"value": "3.14", "type": "float"}),
        MagicMock(key="bool.key", value={"value": "true", "type": "bool"}),
        MagicMock(key="str.key", value={"value": "hello", "type": "str"}),
    ]

    with patch('app.services.config_service.ConfigRepository') as mock_repo_class:
        mock_repo = MagicMock()
        mock_repo.get_all = AsyncMock(return_value=mock_items)
        mock_repo_class.return_value = mock_repo

        await config_service._load_cache()

        assert config_service._cache["int.key"] == 10
        assert config_service._cache["float.key"] == 3.14
        assert config_service._cache["bool.key"] is True
        assert config_service._cache["str.key"] == "hello"
        assert config_service._cache_loaded is True


@pytest.mark.asyncio
async def test_load_cache_handles_fallback_format(config_service, mock_db):
    """Should handle config items without proper structure (fallback)."""
    mock_item = MagicMock(key="fallback.key", value={"raw": "data"})

    with patch('app.services.config_service.ConfigRepository') as mock_repo_class:
        mock_repo = MagicMock()
        mock_repo.get_all = AsyncMock(return_value=[mock_item])
        mock_repo_class.return_value = mock_repo

        await config_service._load_cache()

        # Should store entire JSONB as value
        assert config_service._cache["fallback.key"] == {"raw": "data"}


@pytest.mark.asyncio
async def test_load_cache_empty_database(config_service, mock_db):
    """Should handle empty config table."""
    with patch('app.services.config_service.ConfigRepository') as mock_repo_class:
        mock_repo = MagicMock()
        mock_repo.get_all = AsyncMock(return_value=[])
        mock_repo_class.return_value = mock_repo

        await config_service._load_cache()

        assert config_service._cache == {}
        assert config_service._cache_loaded is True


# Integration Test

@pytest.mark.asyncio
async def test_full_workflow(config_service, mock_db):
    """Test complete workflow: load, get, refresh."""
    # Initial load
    initial_items = [
        MagicMock(key="app.timeout", value={"value": "30", "type": "int"}),
    ]

    # Refreshed load
    refreshed_items = [
        MagicMock(key="app.timeout", value={"value": "60", "type": "int"}),
        MagicMock(key="app.enabled", value={"value": "true", "type": "bool"}),
    ]

    with patch('app.services.config_service.ConfigRepository') as mock_repo_class:
        mock_repo = MagicMock()
        mock_repo.get_all = AsyncMock(side_effect=[initial_items, refreshed_items])
        mock_repo_class.return_value = mock_repo

        # First get - loads cache
        timeout = await config_service.get_config("app.timeout", default=10)
        assert timeout == 30

        # Refresh - reloads with new data
        await config_service.refresh()

        # Get updated values
        timeout = await config_service.get_config("app.timeout")
        enabled = await config_service.get_config("app.enabled")

        assert timeout == 60
        assert enabled is True
        assert mock_repo.get_all.call_count == 2
