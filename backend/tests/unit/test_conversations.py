"""
Unit Tests for Conversation API Endpoints
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.routes.conversations import router
from app.dependencies import get_current_user
from app.api.routes.conversations import get_db

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# Fixtures

@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.password_hash = "hashed"
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    return user


@pytest.fixture
def mock_conversation(mock_user):
    """Create a mock conversation."""
    conv = MagicMock()
    conv.id = uuid4()
    conv.user_id = mock_user.id
    conv.title = "Test Conversation"
    conv.created_at = datetime.utcnow()
    conv.updated_at = datetime.utcnow()
    return conv


@pytest.fixture
def mock_messages(mock_conversation):
    """Create mock messages for a conversation."""
    msg1 = MagicMock()
    msg1.id = uuid4()
    msg1.conversation_id = mock_conversation.id
    msg1.role = "user"
    msg1.content = "Hello"
    msg1.meta_data = {}
    msg1.created_at = datetime.utcnow()

    msg2 = MagicMock()
    msg2.id = uuid4()
    msg2.conversation_id = mock_conversation.id
    msg2.role = "assistant"
    msg2.content = "Hi there!"
    msg2.meta_data = {"intent": "chitchat"}
    msg2.created_at = datetime.utcnow()

    return [msg1, msg2]


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Automatically cleanup dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


# List Conversations Tests

@patch('app.api.routes.conversations.ConversationRepository')
def test_list_conversations_success(mock_repo_class, mock_user, mock_conversation):
    """Should list conversations for authenticated user."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Mock repository
    mock_repo = MagicMock()
    mock_repo.list_by_user = AsyncMock(return_value=[mock_conversation])
    mock_repo_class.return_value = mock_repo

    # Make request
    response = client.get("/api/conversations?limit=50&offset=0")

    # Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert len(data["conversations"]) == 1
    assert data["conversations"][0]["title"] == "Test Conversation"


@patch('app.api.routes.conversations.ConversationRepository')
def test_list_conversations_empty(mock_repo_class, mock_user):
    """Should return empty list when user has no conversations."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Mock repository - empty list
    mock_repo = MagicMock()
    mock_repo.list_by_user = AsyncMock(return_value=[])
    mock_repo_class.return_value = mock_repo

    # Make request
    response = client.get("/api/conversations")

    # Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 0
    assert len(data["conversations"]) == 0


@patch('app.api.routes.conversations.ConversationRepository')
def test_list_conversations_pagination(mock_repo_class, mock_user, mock_conversation):
    """Should respect pagination parameters."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Mock repository
    mock_repo = MagicMock()
    mock_repo.list_by_user = AsyncMock(return_value=[mock_conversation])
    mock_repo_class.return_value = mock_repo

    # Make request with custom pagination
    response = client.get("/api/conversations?limit=10&offset=5")

    # Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 5


# Get Conversation Detail Tests

@patch('app.api.routes.conversations.MessageRepository')
@patch('app.api.routes.conversations.ConversationRepository')
def test_get_conversation_detail_success(mock_conv_repo_class, mock_msg_repo_class,
                                         mock_user, mock_conversation, mock_messages):
    """Should return conversation with messages for owner."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Mock conversation repository
    mock_conv_repo = MagicMock()
    mock_conv_repo.get_by_id = AsyncMock(return_value=mock_conversation)
    mock_conv_repo_class.return_value = mock_conv_repo

    # Mock message repository
    mock_msg_repo = MagicMock()
    mock_msg_repo.list_by_conversation = AsyncMock(return_value=mock_messages)
    mock_msg_repo_class.return_value = mock_msg_repo

    # Make request
    response = client.get(f"/api/conversations/{mock_conversation.id}")

    # Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["conversation"]["id"] == str(mock_conversation.id)
    assert data["conversation"]["title"] == "Test Conversation"
    assert len(data["messages"]) == 2


@patch('app.api.routes.conversations.ConversationRepository')
def test_get_conversation_detail_not_found(mock_repo_class, mock_user):
    """Should return 404 when conversation doesn't exist."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Mock repository - conversation not found
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)
    mock_repo_class.return_value = mock_repo

    # Make request with random UUID
    conversation_id = uuid4()
    response = client.get(f"/api/conversations/{conversation_id}")

    # Assertions
    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch('app.api.routes.conversations.ConversationRepository')
def test_get_conversation_detail_access_denied(mock_repo_class, mock_user, mock_conversation):
    """Should return 403 when user doesn't own conversation."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Mock conversation with different owner
    mock_conversation.user_id = uuid4()

    # Mock repository
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_conversation)
    mock_repo_class.return_value = mock_repo

    # Make request
    response = client.get(f"/api/conversations/{mock_conversation.id}")

    # Assertions
    assert response.status_code == status.HTTP_403_FORBIDDEN


# Create Conversation Tests

@patch('app.api.routes.conversations.ConversationRepository')
def test_create_conversation_with_title(mock_repo_class, mock_user, mock_conversation, mock_db):
    """Should create conversation with provided title."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    # Mock repository
    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value=mock_conversation)
    mock_repo_class.return_value = mock_repo

    # Make request
    response = client.post(
        "/api/conversations",
        json={"title": "My Custom Title"}
    )

    # Assertions
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] == str(mock_conversation.id)


@patch('app.api.routes.conversations.ConversationRepository')
def test_create_conversation_auto_title(mock_repo_class, mock_user, mock_conversation, mock_db):
    """Should auto-generate title when not provided."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    # Mock repository
    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value=mock_conversation)
    mock_repo_class.return_value = mock_repo

    # Make request without title
    response = client.post("/api/conversations", json={})

    # Assertions
    assert response.status_code == status.HTTP_201_CREATED


# Delete Conversation Tests

@patch('app.api.routes.conversations.ConversationRepository')
def test_delete_conversation_success(mock_repo_class, mock_user, mock_conversation, mock_db):
    """Should delete conversation when user owns it."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    # Mock repository
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_conversation)
    mock_repo.delete = AsyncMock()
    mock_repo_class.return_value = mock_repo

    # Make request
    response = client.delete(f"/api/conversations/{mock_conversation.id}")

    # Assertions
    assert response.status_code == status.HTTP_204_NO_CONTENT


@patch('app.api.routes.conversations.ConversationRepository')
def test_delete_conversation_not_found(mock_repo_class, mock_user):
    """Should return 404 when conversation doesn't exist."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Mock repository - conversation not found
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)
    mock_repo_class.return_value = mock_repo

    # Make request with random UUID
    conversation_id = uuid4()
    response = client.delete(f"/api/conversations/{conversation_id}")

    # Assertions
    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch('app.api.routes.conversations.ConversationRepository')
def test_delete_conversation_access_denied(mock_repo_class, mock_user, mock_conversation):
    """Should return 403 when user doesn't own conversation."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Mock conversation with different owner
    mock_conversation.user_id = uuid4()

    # Mock repository
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_conversation)
    mock_repo_class.return_value = mock_repo

    # Make request
    response = client.delete(f"/api/conversations/{mock_conversation.id}")

    # Assertions
    assert response.status_code == status.HTTP_403_FORBIDDEN


# Edge Cases

def test_list_conversations_invalid_pagination(mock_user):
    """Should reject invalid pagination parameters."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # limit too high
    response = client.get("/api/conversations?limit=101")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # negative offset
    response = client.get("/api/conversations?offset=-1")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # limit too low
    response = client.get("/api/conversations?limit=0")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_conversation_detail_invalid_uuid(mock_user):
    """Should reject invalid UUID format."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    response = client.get("/api/conversations/invalid-uuid")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_conversation_title_too_long(mock_user):
    """Should reject title longer than 200 characters."""
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user

    long_title = "a" * 201
    response = client.post("/api/conversations", json={"title": long_title})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
