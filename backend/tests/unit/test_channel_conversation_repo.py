"""
Unit Tests for ChannelConversationRepository
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Channel, ChannelConversation
from app.db.repositories.channel_repo import ChannelRepository
from app.db.repositories.channel_conversation_repo import ChannelConversationRepository


@pytest_asyncio.fixture
async def test_channel(db_session: AsyncSession, test_user: User) -> Channel:
    """Fixture to create a test channel."""
    repo = ChannelRepository(db_session)
    channel = await repo.create(
        name="test-channel",
        display_title="Test Channel",
        description="Test Description",
        created_by=test_user.id,
        qdrant_collection_name="channel_test_channel"
    )
    await db_session.commit()
    return channel


@pytest.mark.asyncio
async def test_get_or_create_new_conversation(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel
):
    """Test get_or_create creates new conversation when none exists."""
    repo = ChannelConversationRepository(db_session)

    conversation = await repo.get_or_create(
        channel_id=test_channel.id,
        user_id=test_user.id
    )

    assert conversation.id is not None
    assert conversation.channel_id == test_channel.id
    assert conversation.user_id == test_user.id
    assert conversation.created_at is not None
    assert conversation.updated_at is not None


@pytest.mark.asyncio
async def test_get_or_create_existing_conversation(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel
):
    """Test get_or_create returns existing conversation."""
    repo = ChannelConversationRepository(db_session)

    # Create first conversation
    conv1 = await repo.get_or_create(
        channel_id=test_channel.id,
        user_id=test_user.id
    )
    await db_session.flush()

    # Get same conversation again
    conv2 = await repo.get_or_create(
        channel_id=test_channel.id,
        user_id=test_user.id
    )

    assert conv1.id == conv2.id
    assert conv1.channel_id == conv2.channel_id
    assert conv1.user_id == conv2.user_id


@pytest.mark.asyncio
async def test_get_by_id_found(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel
):
    """Test retrieving conversation by ID when it exists."""
    repo = ChannelConversationRepository(db_session)

    created = await repo.get_or_create(
        channel_id=test_channel.id,
        user_id=test_user.id
    )
    await db_session.flush()

    retrieved = await repo.get_by_id(created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.channel_id == test_channel.id
    assert retrieved.user_id == test_user.id


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    """Test get_by_id returns None for non-existent conversation."""
    from uuid import uuid4
    repo = ChannelConversationRepository(db_session)

    result = await repo.get_by_id(uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_list_by_user_empty(
    db_session: AsyncSession,
    test_user: User
):
    """Test listing conversations when user has none."""
    repo = ChannelConversationRepository(db_session)

    conversations, total = await repo.list_by_user(
        user_id=test_user.id,
        limit=10,
        offset=0
    )

    assert len(conversations) == 0
    assert total == 0


@pytest.mark.asyncio
async def test_list_by_user_with_conversations(
    db_session: AsyncSession,
    test_user: User
):
    """Test listing conversations for a user."""
    repo = ChannelConversationRepository(db_session)
    channel_repo = ChannelRepository(db_session)

    # Create multiple channels
    channel1 = await channel_repo.create(
        name="channel-1",
        display_title="Channel 1",
        description=None,
        created_by=test_user.id,
        qdrant_collection_name="channel_channel_1"
    )
    channel2 = await channel_repo.create(
        name="channel-2",
        display_title="Channel 2",
        description=None,
        created_by=test_user.id,
        qdrant_collection_name="channel_channel_2"
    )

    # Create conversations
    await repo.get_or_create(channel1.id, test_user.id)
    await repo.get_or_create(channel2.id, test_user.id)

    # List conversations
    conversations, total = await repo.list_by_user(
        user_id=test_user.id,
        limit=10,
        offset=0
    )

    assert len(conversations) == 2
    assert total == 2


@pytest.mark.asyncio
async def test_list_by_user_pagination(
    db_session: AsyncSession,
    test_user: User
):
    """Test listing conversations with pagination."""
    repo = ChannelConversationRepository(db_session)
    channel_repo = ChannelRepository(db_session)

    # Create 5 channels and conversations
    for i in range(5):
        channel = await channel_repo.create(
            name=f"channel-{i}",
            display_title=f"Channel {i}",
            description=None,
            created_by=test_user.id,
            qdrant_collection_name=f"channel_channel_{i}"
        )
        await repo.get_or_create(channel.id, test_user.id)

    # Get first page
    page1, total = await repo.list_by_user(test_user.id, limit=2, offset=0)
    assert total == 5
    assert len(page1) == 2

    # Get second page
    page2, total = await repo.list_by_user(test_user.id, limit=2, offset=2)
    assert total == 5
    assert len(page2) == 2

    # Ensure different conversations
    assert page1[0].id != page2[0].id


@pytest.mark.asyncio
async def test_update_timestamp(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel
):
    """Test updating conversation timestamp."""
    import asyncio

    repo = ChannelConversationRepository(db_session)

    # Create conversation
    conversation = await repo.get_or_create(
        channel_id=test_channel.id,
        user_id=test_user.id
    )
    await db_session.flush()

    original_updated_at = conversation.updated_at

    # Small delay to ensure timestamp difference
    await asyncio.sleep(0.01)

    # Update timestamp
    await repo.update_timestamp(conversation.id)
    await db_session.flush()
    await db_session.refresh(conversation)

    # Verify timestamp was updated
    assert conversation.updated_at > original_updated_at


@pytest.mark.asyncio
async def test_list_by_user_ordered_by_updated_at(
    db_session: AsyncSession,
    test_user: User
):
    """Test that list_by_user returns conversations ordered by updated_at DESC."""
    import asyncio

    repo = ChannelConversationRepository(db_session)
    channel_repo = ChannelRepository(db_session)

    # Create 3 channels and conversations
    conversations = []
    for i in range(3):
        channel = await channel_repo.create(
            name=f"conv-{i}",
            display_title=f"Conv {i}",
            description=None,
            created_by=test_user.id,
            qdrant_collection_name=f"channel_conv_{i}"
        )
        conv = await repo.get_or_create(channel.id, test_user.id)
        await db_session.flush()
        conversations.append(conv)
        await asyncio.sleep(0.01)  # Ensure distinct timestamps

    # Update middle conversation to make it most recent
    await repo.update_timestamp(conversations[1].id)
    await db_session.flush()

    # List conversations
    listed, total = await repo.list_by_user(test_user.id, limit=10, offset=0)

    assert total == 3
    # Most recently updated should be first
    assert listed[0].id == conversations[1].id
