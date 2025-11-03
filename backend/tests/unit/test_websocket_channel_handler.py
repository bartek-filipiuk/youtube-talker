"""
Unit Tests for WebSocket Channel Handler

Tests for detect_conversation_type() helper function and channel-aware message retrieval.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Conversation, ChannelConversation, Channel
from app.api.websocket.chat_handler import detect_conversation_type
from app.core.errors import (
    ConversationNotFoundError,
    ConversationAccessDeniedError,
    ChannelNotFoundError,
)
from app.db.repositories.conversation_repo import ConversationRepository
from app.db.repositories.channel_repo import ChannelRepository
from app.db.repositories.channel_conversation_repo import ChannelConversationRepository


@pytest.mark.asyncio
async def test_detect_conversation_type_personal(db_session: AsyncSession, test_user: User, test_conversation: Conversation):
    """Test detecting personal conversation type."""
    conv_type, conversation, channel = await detect_conversation_type(
        conversation_id=test_conversation.id,
        user_id=test_user.id,
        db=db_session
    )

    assert conv_type == "personal"
    assert conversation.id == test_conversation.id
    assert isinstance(conversation, Conversation)
    assert channel is None


@pytest.mark.asyncio
async def test_detect_conversation_type_channel(db_session: AsyncSession, test_user: User):
    """Test detecting channel conversation type."""
    # Create channel
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.create(
        name="test-channel",
        display_title="Test Channel",
        description="Test channel description",
        created_by=test_user.id,
        qdrant_collection_name="channel_test_channel",
    )
    await db_session.flush()

    # Create channel conversation
    channel_conv_repo = ChannelConversationRepository(db_session)
    channel_conv = await channel_conv_repo.get_or_create(
        channel_id=channel.id,
        user_id=test_user.id,
    )
    await db_session.flush()
    await db_session.commit()

    # Detect type
    conv_type, conversation, detected_channel = await detect_conversation_type(
        conversation_id=channel_conv.id,
        user_id=test_user.id,
        db=db_session
    )

    assert conv_type == "channel"
    assert conversation.id == channel_conv.id
    assert isinstance(conversation, ChannelConversation)
    assert detected_channel is not None
    assert detected_channel.id == channel.id
    assert detected_channel.name == "test-channel"


@pytest.mark.asyncio
async def test_detect_conversation_not_found(db_session: AsyncSession, test_user: User):
    """Test detecting conversation that doesn't exist."""
    fake_uuid = uuid4()

    with pytest.raises(ConversationNotFoundError) as exc_info:
        await detect_conversation_type(
            conversation_id=fake_uuid,
            user_id=test_user.id,
            db=db_session
        )

    assert str(fake_uuid) in str(exc_info.value)


@pytest.mark.asyncio
async def test_detect_conversation_access_denied_personal(db_session: AsyncSession, test_user: User):
    """Test detecting personal conversation owned by different user."""
    # Create another user
    other_user = User(
        email="other@example.com",
        password_hash="fakehash"
    )
    db_session.add(other_user)
    await db_session.flush()

    # Create conversation for other user
    conversation_repo = ConversationRepository(db_session)
    other_conversation = await conversation_repo.create(
        user_id=other_user.id,
        title="Other User's Conversation"
    )
    await db_session.commit()

    # Try to access with test_user
    with pytest.raises(ConversationAccessDeniedError) as exc_info:
        await detect_conversation_type(
            conversation_id=other_conversation.id,
            user_id=test_user.id,
            db=db_session
        )

    assert "does not have access" in str(exc_info.value)


@pytest.mark.asyncio
async def test_detect_conversation_access_denied_channel(db_session: AsyncSession, test_user: User):
    """Test detecting channel conversation owned by different user."""
    # Create another user
    other_user = User(
        email="other@example.com",
        password_hash="fakehash"
    )
    db_session.add(other_user)
    await db_session.flush()

    # Create channel
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.create(
        name="test-channel",
        display_title="Test Channel",
        description="Test",
        created_by=test_user.id,
        qdrant_collection_name="channel_test",
    )
    await db_session.flush()

    # Create channel conversation for other user
    channel_conv_repo = ChannelConversationRepository(db_session)
    other_channel_conv = await channel_conv_repo.get_or_create(
        channel_id=channel.id,
        user_id=other_user.id,
    )
    await db_session.commit()

    # Try to access with test_user
    with pytest.raises(ConversationAccessDeniedError) as exc_info:
        await detect_conversation_type(
            conversation_id=other_channel_conv.id,
            user_id=test_user.id,
            db=db_session
        )

    assert "does not have access" in str(exc_info.value)


@pytest.mark.asyncio
async def test_detect_conversation_channel_deleted(db_session: AsyncSession, test_user: User):
    """Test detecting channel conversation where channel has been soft-deleted."""
    # Create channel
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.create(
        name="deleted-channel",
        display_title="Deleted Channel",
        description="This will be deleted",
        created_by=test_user.id,
        qdrant_collection_name="channel_deleted",
    )
    await db_session.flush()

    # Create channel conversation
    channel_conv_repo = ChannelConversationRepository(db_session)
    channel_conv = await channel_conv_repo.get_or_create(
        channel_id=channel.id,
        user_id=test_user.id,
    )
    await db_session.flush()

    # Soft delete the channel
    await channel_repo.soft_delete(channel.id)
    await db_session.commit()

    # Try to detect conversation type
    with pytest.raises(ChannelNotFoundError) as exc_info:
        await detect_conversation_type(
            conversation_id=channel_conv.id,
            user_id=test_user.id,
            db=db_session
        )

    assert "no longer available" in str(exc_info.value)


@pytest.mark.asyncio
async def test_detect_conversation_type_with_multiple_users(db_session: AsyncSession, test_user: User):
    """Test that multiple users can have their own conversations with the same channel."""
    # Create another user
    user2 = User(
        email="user2@example.com",
        password_hash="fakehash"
    )
    db_session.add(user2)
    await db_session.flush()

    # Create channel
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.create(
        name="shared-channel",
        display_title="Shared Channel",
        description="Multiple users can chat here",
        created_by=test_user.id,
        qdrant_collection_name="channel_shared",
    )
    await db_session.flush()

    # Create channel conversations for both users
    channel_conv_repo = ChannelConversationRepository(db_session)
    conv1 = await channel_conv_repo.get_or_create(
        channel_id=channel.id,
        user_id=test_user.id,
    )
    conv2 = await channel_conv_repo.get_or_create(
        channel_id=channel.id,
        user_id=user2.id,
    )
    await db_session.commit()

    # Verify user1's conversation
    conv_type1, conversation1, channel1 = await detect_conversation_type(
        conversation_id=conv1.id,
        user_id=test_user.id,
        db=db_session
    )
    assert conv_type1 == "channel"
    assert conversation1.user_id == test_user.id
    assert channel1.id == channel.id

    # Verify user2's conversation
    conv_type2, conversation2, channel2 = await detect_conversation_type(
        conversation_id=conv2.id,
        user_id=user2.id,
        db=db_session
    )
    assert conv_type2 == "channel"
    assert conversation2.user_id == user2.id
    assert channel2.id == channel.id

    # Verify conversations are distinct
    assert conv1.id != conv2.id
