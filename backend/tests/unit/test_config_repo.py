"""
Unit Tests for ConfigRepository
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.config_repo import ConfigRepository


@pytest.mark.asyncio
async def test_set_value(db_session: AsyncSession):
    """Test setting a config value."""
    repo = ConfigRepository(db_session)
    config = await repo.set_value(
        key="max_chunk_size", value={"size": 700, "overlap": 20}
    )

    assert config.key == "max_chunk_size"
    assert config.value == {"size": 700, "overlap": 20}


@pytest.mark.asyncio
async def test_get_value(db_session: AsyncSession):
    """Test retrieving a config value by key."""
    repo = ConfigRepository(db_session)

    # Set value
    await repo.set_value(key="test_key", value={"data": "test"})

    # Get value
    value = await repo.get_value("test_key")

    assert value is not None
    assert value == {"data": "test"}


@pytest.mark.asyncio
async def test_get_value_not_found(db_session: AsyncSession):
    """Test retrieving non-existent key returns None."""
    repo = ConfigRepository(db_session)
    value = await repo.get_value("nonexistent_key")

    assert value is None


@pytest.mark.asyncio
async def test_set_value_upsert(db_session: AsyncSession):
    """Test that set_value updates existing key (upsert behavior)."""
    repo = ConfigRepository(db_session)

    # Set initial value
    await repo.set_value(key="update_test", value={"version": 1})

    # Update value
    await repo.set_value(key="update_test", value={"version": 2})

    # Verify updated value
    value = await repo.get_value("update_test")
    assert value == {"version": 2}

    # Verify only one record exists (not duplicated)
    from sqlalchemy import select, func
    from app.db.models import Config

    result = await db_session.execute(
        select(func.count()).select_from(Config).where(Config.key == "update_test")
    )
    count = result.scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_set_multiple_configs(db_session: AsyncSession):
    """Test setting multiple different config keys."""
    repo = ConfigRepository(db_session)

    # Set multiple configs
    await repo.set_value(key="config1", value={"a": 1})
    await repo.set_value(key="config2", value={"b": 2})
    await repo.set_value(key="config3", value={"c": 3})

    # Retrieve all
    val1 = await repo.get_value("config1")
    val2 = await repo.get_value("config2")
    val3 = await repo.get_value("config3")

    assert val1 == {"a": 1}
    assert val2 == {"b": 2}
    assert val3 == {"c": 3}


@pytest.mark.asyncio
async def test_delete_config(db_session: AsyncSession):
    """Test deleting a config entry."""
    from sqlalchemy import delete
    from app.db.models import Config

    repo = ConfigRepository(db_session)

    # Create config
    config = await repo.set_value(key="delete_me", value={"test": "data"})

    # Delete config directly (Config uses 'key' as primary key, not 'id')
    await db_session.execute(delete(Config).where(Config.key == "delete_me"))
    await db_session.flush()

    # Verify deleted
    value = await repo.get_value("delete_me")
    assert value is None
