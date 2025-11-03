"""
Unit Tests for ChannelRepository
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Channel
from app.db.repositories.channel_repo import ChannelRepository


@pytest.mark.asyncio
async def test_create_channel(db_session: AsyncSession, test_user: User):
    """Test creating a new channel."""
    repo = ChannelRepository(db_session)
    channel = await repo.create(
        name="python-basics",
        display_title="Python Basics",
        description="Learn Python fundamentals",
        created_by=test_user.id,
        qdrant_collection_name="channel_python_basics"
    )

    assert channel.id is not None
    assert channel.name == "python-basics"
    assert channel.display_title == "Python Basics"
    assert channel.description == "Learn Python fundamentals"
    assert channel.created_by == test_user.id
    assert channel.qdrant_collection_name == "channel_python_basics"
    assert channel.is_active is True
    assert channel.created_at is not None


@pytest.mark.asyncio
async def test_create_channel_without_optional_fields(db_session: AsyncSession):
    """Test creating channel with minimal fields."""
    repo = ChannelRepository(db_session)
    channel = await repo.create(
        name="minimal-channel",
        display_title="Minimal Channel",
        description=None,
        created_by=None,
        qdrant_collection_name="channel_minimal_channel"
    )

    assert channel.id is not None
    assert channel.description is None
    assert channel.created_by is None


@pytest.mark.asyncio
async def test_get_channel_by_id(db_session: AsyncSession, test_user: User):
    """Test retrieving channel by ID."""
    repo = ChannelRepository(db_session)
    created = await repo.create(
        name="test-channel",
        display_title="Test Channel",
        description="Test",
        created_by=test_user.id,
        qdrant_collection_name="channel_test_channel"
    )

    channel = await repo.get_by_id(created.id)
    assert channel is not None
    assert channel.id == created.id
    assert channel.name == "test-channel"


@pytest.mark.asyncio
async def test_get_channel_by_id_not_found(db_session: AsyncSession):
    """Test get_by_id returns None for non-existent channel."""
    from uuid import uuid4
    repo = ChannelRepository(db_session)
    channel = await repo.get_by_id(uuid4())
    assert channel is None


@pytest.mark.asyncio
async def test_get_channel_by_name(db_session: AsyncSession, test_user: User):
    """Test retrieving channel by unique name."""
    repo = ChannelRepository(db_session)
    await repo.create(
        name="unique-name",
        display_title="Unique Channel",
        description=None,
        created_by=test_user.id,
        qdrant_collection_name="channel_unique_name"
    )

    channel = await repo.get_by_name("unique-name")
    assert channel is not None
    assert channel.name == "unique-name"


@pytest.mark.asyncio
async def test_get_channel_by_name_not_found(db_session: AsyncSession):
    """Test get_by_name returns None for non-existent name."""
    repo = ChannelRepository(db_session)
    channel = await repo.get_by_name("non-existent")
    assert channel is None


@pytest.mark.asyncio
async def test_list_active_channels(db_session: AsyncSession, test_user: User):
    """Test listing only active channels."""
    repo = ChannelRepository(db_session)

    # Create active channel
    active1 = await repo.create(
        name="active-1",
        display_title="Active 1",
        description=None,
        created_by=test_user.id,
        qdrant_collection_name="channel_active_1"
    )

    # Create another active channel
    active2 = await repo.create(
        name="active-2",
        display_title="Active 2",
        description=None,
        created_by=test_user.id,
        qdrant_collection_name="channel_active_2"
    )

    # Create inactive channel
    inactive = await repo.create(
        name="inactive",
        display_title="Inactive",
        description=None,
        created_by=test_user.id,
        qdrant_collection_name="channel_inactive"
    )
    await repo.soft_delete(inactive.id)

    # List active channels
    channels, total = await repo.list_active(limit=10, offset=0)

    assert total == 2
    assert len(channels) == 2
    channel_names = {c.name for c in channels}
    assert "active-1" in channel_names
    assert "active-2" in channel_names
    assert "inactive" not in channel_names


@pytest.mark.asyncio
async def test_list_active_channels_pagination(db_session: AsyncSession, test_user: User):
    """Test active channel listing with pagination."""
    repo = ChannelRepository(db_session)

    # Create 5 active channels
    for i in range(5):
        await repo.create(
            name=f"channel-{i}",
            display_title=f"Channel {i}",
            description=None,
            created_by=test_user.id,
            qdrant_collection_name=f"channel_channel_{i}"
        )

    # Get first page
    page1, total = await repo.list_active(limit=2, offset=0)
    assert total == 5
    assert len(page1) == 2

    # Get second page
    page2, total = await repo.list_active(limit=2, offset=2)
    assert total == 5
    assert len(page2) == 2

    # Ensure different channels
    assert page1[0].id != page2[0].id


@pytest.mark.asyncio
async def test_list_all_channels(db_session: AsyncSession, test_user: User):
    """Test listing all channels including inactive."""
    repo = ChannelRepository(db_session)

    # Create active channel
    await repo.create(
        name="active",
        display_title="Active",
        description=None,
        created_by=test_user.id,
        qdrant_collection_name="channel_active"
    )

    # Create inactive channel
    inactive = await repo.create(
        name="inactive",
        display_title="Inactive",
        description=None,
        created_by=test_user.id,
        qdrant_collection_name="channel_inactive"
    )
    await repo.soft_delete(inactive.id)

    # List all channels
    channels, total = await repo.list_all(limit=10, offset=0)

    assert total == 2
    assert len(channels) == 2


@pytest.mark.asyncio
async def test_update_channel(db_session: AsyncSession, test_user: User):
    """Test updating channel fields."""
    repo = ChannelRepository(db_session)
    channel = await repo.create(
        name="update-test",
        display_title="Original Title",
        description="Original Description",
        created_by=test_user.id,
        qdrant_collection_name="channel_update_test"
    )

    # Update channel
    updated = await repo.update(
        channel_id=channel.id,
        display_title="Updated Title",
        description="Updated Description"
    )

    assert updated.id == channel.id
    assert updated.display_title == "Updated Title"
    assert updated.description == "Updated Description"
    assert updated.name == "update-test"  # Name should not change


@pytest.mark.asyncio
async def test_update_channel_partial(db_session: AsyncSession, test_user: User):
    """Test updating only display_title."""
    repo = ChannelRepository(db_session)
    channel = await repo.create(
        name="partial-update",
        display_title="Original",
        description="Original Desc",
        created_by=test_user.id,
        qdrant_collection_name="channel_partial_update"
    )

    # Update only title
    updated = await repo.update(
        channel_id=channel.id,
        display_title="New Title",
        description=None
    )

    assert updated.display_title == "New Title"
    assert updated.description is None


@pytest.mark.asyncio
async def test_soft_delete_channel(db_session: AsyncSession, test_user: User):
    """Test soft deleting a channel."""
    repo = ChannelRepository(db_session)
    channel = await repo.create(
        name="delete-test",
        display_title="Delete Test",
        description=None,
        created_by=test_user.id,
        qdrant_collection_name="channel_delete_test"
    )

    # Soft delete
    result = await repo.soft_delete(channel.id)
    assert result is True

    # Verify still exists but inactive
    deleted = await repo.get_by_id(channel.id)
    assert deleted is not None
    assert deleted.is_active is False


@pytest.mark.asyncio
async def test_soft_delete_nonexistent_channel(db_session: AsyncSession):
    """Test soft delete returns False for non-existent channel."""
    from uuid import uuid4
    repo = ChannelRepository(db_session)
    result = await repo.soft_delete(uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_reactivate_channel(db_session: AsyncSession, test_user: User):
    """Test reactivating a soft-deleted channel."""
    repo = ChannelRepository(db_session)
    channel = await repo.create(
        name="reactivate-test",
        display_title="Reactivate Test",
        description=None,
        created_by=test_user.id,
        qdrant_collection_name="channel_reactivate_test"
    )

    # Soft delete then reactivate
    await repo.soft_delete(channel.id)
    result = await repo.reactivate(channel.id)
    assert result is True

    # Verify active again
    reactivated = await repo.get_by_id(channel.id)
    assert reactivated is not None
    assert reactivated.is_active is True


@pytest.mark.asyncio
async def test_reactivate_nonexistent_channel(db_session: AsyncSession):
    """Test reactivate returns False for non-existent channel."""
    from uuid import uuid4
    repo = ChannelRepository(db_session)
    result = await repo.reactivate(uuid4())
    assert result is False
