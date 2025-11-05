"""
Unit Tests for MessageRepository
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation
from app.db.repositories.message_repo import MessageRepository


@pytest.mark.asyncio
async def test_create_message(db_session: AsyncSession, test_conversation: Conversation):
    """Test creating a new message."""
    repo = MessageRepository(db_session)
    message = await repo.create(
        conversation_id=test_conversation.id,
        role="user",
        content="Hello, world!",
        meta_data={"source": "test"},
    )

    assert message.id is not None
    assert message.conversation_id == test_conversation.id
    assert message.role == "user"
    assert message.content == "Hello, world!"
    assert message.meta_data == {"source": "test"}


@pytest.mark.asyncio
async def test_create_message_without_metadata(
    db_session: AsyncSession, test_conversation: Conversation
):
    """Test creating message without metadata."""
    repo = MessageRepository(db_session)
    message = await repo.create(
        conversation_id=test_conversation.id, role="assistant", content="Response"
    )

    assert message.meta_data == {}


@pytest.mark.asyncio
async def test_list_messages_by_conversation(
    db_session: AsyncSession, test_conversation: Conversation
):
    """Test listing messages for a conversation."""
    repo = MessageRepository(db_session)

    # Create messages
    msg1 = await repo.create(
        conversation_id=test_conversation.id, role="user", content="First"
    )
    msg2 = await repo.create(
        conversation_id=test_conversation.id, role="assistant", content="Second"
    )

    # List messages
    messages = await repo.list_by_conversation(test_conversation.id)

    assert len(messages) == 2
    # Should be ordered by created_at ASC (oldest first)
    assert messages[0].id == msg1.id
    assert messages[1].id == msg2.id


@pytest.mark.asyncio
async def test_get_last_n_messages(db_session: AsyncSession, test_conversation: Conversation):
    """Test getting last N messages from conversation."""
    repo = MessageRepository(db_session)

    # Create 5 messages
    for i in range(5):
        await repo.create(
            conversation_id=test_conversation.id, role="user", content=f"Message {i}"
        )

    # Get last 3 (returns List[dict] with {role, content})
    last_3 = await repo.get_last_n(n=3, conversation_id=test_conversation.id)

    assert len(last_3) == 3
    # Verify all returned messages have expected structure
    for msg in last_3:
        assert "role" in msg
        assert "content" in msg
        assert msg["role"] == "user"
        assert msg["content"].startswith("Message ")


@pytest.mark.asyncio
async def test_messages_cascade_delete_with_conversation(
    db_session: AsyncSession, test_conversation: Conversation
):
    """Test that messages are deleted when conversation is deleted."""
    repo = MessageRepository(db_session)

    # Create message
    message = await repo.create(
        conversation_id=test_conversation.id, role="user", content="Test"
    )

    # Delete conversation
    from app.db.repositories.conversation_repo import ConversationRepository

    conv_repo = ConversationRepository(db_session)
    await conv_repo.delete(test_conversation.id)

    # Verify message is also deleted
    deleted_message = await repo.get_by_id(message.id)
    assert deleted_message is None


@pytest.mark.asyncio
async def test_list_by_channel_conversation(db_session: AsyncSession, test_user):
    """Test listing messages for a channel conversation."""
    from app.db.repositories.channel_conversation_repo import ChannelConversationRepository
    from app.db.repositories.channel_repo import ChannelRepository
    from app.db.models import Message

    # Create channel
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.create(
        name="python-tutorials",
        display_title="Python Tutorials",
        description="Learn Python",
        created_by=test_user.id,
        qdrant_collection_name="channel_python_tutorials",
    )
    await db_session.flush()

    # Create channel conversation
    channel_conv_repo = ChannelConversationRepository(db_session)
    channel_conv = await channel_conv_repo.get_or_create(
        channel_id=channel.id,
        user_id=test_user.id,
    )
    await db_session.flush()

    # Create messages for channel conversation
    msg1 = Message(
        channel_conversation_id=channel_conv.id,
        role="user",
        content="What is Python?",
        meta_data={},
    )
    msg2 = Message(
        channel_conversation_id=channel_conv.id,
        role="assistant",
        content="Python is a programming language.",
        meta_data={},
    )
    db_session.add(msg1)
    db_session.add(msg2)
    await db_session.flush()

    # List messages
    repo = MessageRepository(db_session)
    messages = await repo.list_by_channel_conversation(channel_conv.id)

    assert len(messages) == 2
    # Should be ordered by created_at ASC (oldest first)
    assert messages[0].content == "What is Python?"
    assert messages[1].content == "Python is a programming language."
    assert messages[0].channel_conversation_id == channel_conv.id
    assert messages[1].channel_conversation_id == channel_conv.id


@pytest.mark.asyncio
async def test_list_by_channel_conversation_empty(db_session: AsyncSession, test_user):
    """Test listing messages for an empty channel conversation."""
    from app.db.repositories.channel_conversation_repo import ChannelConversationRepository
    from app.db.repositories.channel_repo import ChannelRepository

    # Create channel
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.create(
        name="empty-channel",
        display_title="Empty Channel",
        description="No videos",
        created_by=test_user.id,
        qdrant_collection_name="channel_empty_channel",
    )
    await db_session.flush()

    # Create channel conversation without messages
    channel_conv_repo = ChannelConversationRepository(db_session)
    channel_conv = await channel_conv_repo.get_or_create(
        channel_id=channel.id,
        user_id=test_user.id,
    )
    await db_session.flush()

    # List messages (should be empty)
    repo = MessageRepository(db_session)
    messages = await repo.list_by_channel_conversation(channel_conv.id)

    assert len(messages) == 0
