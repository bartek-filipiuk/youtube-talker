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
    last_3 = await repo.get_last_n(test_conversation.id, n=3)

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
