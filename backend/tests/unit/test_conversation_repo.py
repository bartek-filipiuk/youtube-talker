"""
Unit Tests for ConversationRepository
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Conversation
from app.db.repositories.conversation_repo import ConversationRepository


@pytest.mark.asyncio
async def test_create_conversation(db_session: AsyncSession, test_user: User):
    """Test creating a new conversation."""
    repo = ConversationRepository(db_session)
    conversation = await repo.create(user_id=test_user.id, title="My Conversation")

    assert conversation.id is not None
    assert conversation.user_id == test_user.id
    assert conversation.title == "My Conversation"
    assert conversation.created_at is not None


@pytest.mark.asyncio
async def test_create_conversation_without_title(db_session: AsyncSession, test_user: User):
    """Test creating conversation without title."""
    repo = ConversationRepository(db_session)
    conversation = await repo.create(user_id=test_user.id)

    assert conversation.id is not None
    assert conversation.title is None


@pytest.mark.asyncio
async def test_get_conversation_by_id(db_session: AsyncSession, test_conversation: Conversation):
    """Test retrieving conversation by ID."""
    repo = ConversationRepository(db_session)
    conversation = await repo.get_by_id(test_conversation.id)

    assert conversation is not None
    assert conversation.id == test_conversation.id
    assert conversation.title == test_conversation.title


@pytest.mark.asyncio
async def test_list_conversations_by_user(db_session: AsyncSession, test_user: User):
    """Test listing all conversations for a user."""
    repo = ConversationRepository(db_session)

    # Create multiple conversations
    conv1 = await repo.create(user_id=test_user.id, title="First")
    conv2 = await repo.create(user_id=test_user.id, title="Second")

    # List conversations
    conversations = await repo.list_by_user(test_user.id)

    assert len(conversations) == 2
    # Check that both conversations are present (order may vary since created at same time)
    conv_ids = {c.id for c in conversations}
    assert conv1.id in conv_ids
    assert conv2.id in conv_ids


@pytest.mark.asyncio
async def test_list_conversations_pagination(db_session: AsyncSession, test_user: User):
    """Test conversation listing with pagination."""
    repo = ConversationRepository(db_session)

    # Create 5 conversations
    for i in range(5):
        await repo.create(user_id=test_user.id, title=f"Conv {i}")

    # Get first 2
    page1 = await repo.list_by_user(test_user.id, limit=2, offset=0)
    assert len(page1) == 2

    # Get next 2
    page2 = await repo.list_by_user(test_user.id, limit=2, offset=2)
    assert len(page2) == 2

    # Ensure different conversations
    assert page1[0].id != page2[0].id


@pytest.mark.asyncio
async def test_delete_conversation(db_session: AsyncSession, test_conversation: Conversation):
    """Test deleting a conversation."""
    repo = ConversationRepository(db_session)
    result = await repo.delete(test_conversation.id)

    assert result is True

    # Verify deleted
    conversation = await repo.get_by_id(test_conversation.id)
    assert conversation is None
