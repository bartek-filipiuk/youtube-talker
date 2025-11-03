"""
Unit Tests for Channel Public Pydantic Schemas

Tests for user-facing channel API schemas (reduced scope - critical validations only).
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.channel_public import (
    ChannelPublicResponse,
    VideoInChannelResponse,
    ChannelVideoListResponse,
    ChannelListResponse,
    ChannelConversationResponse,
    ChannelConversationDetailResponse,
    ChannelConversationListResponse,
)
from app.schemas.conversation import MessageResponse


def test_channel_public_response_from_orm():
    """Test ChannelPublicResponse serialization from ORM-like dict."""
    data = {
        "id": uuid4(),
        "name": "python-tutorials",
        "display_title": "Python Tutorials",
        "description": "Learn Python programming",
        "video_count": 42,
        "created_at": datetime.now(timezone.utc),
    }

    response = ChannelPublicResponse(**data)

    assert str(response.id) == str(data["id"])
    assert response.name == "python-tutorials"
    assert response.display_title == "Python Tutorials"
    assert response.description == "Learn Python programming"
    assert response.video_count == 42
    assert response.created_at == data["created_at"]


def test_video_in_channel_response_serialization():
    """Test VideoInChannelResponse serialization."""
    transcript_id = uuid4()
    data = {
        "transcript_id": transcript_id,
        "youtube_video_id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up",
        "channel_name": "Rick Astley",
        "duration": 212,
        "added_at": datetime.now(timezone.utc),
    }

    response = VideoInChannelResponse(**data)

    assert str(response.transcript_id) == str(transcript_id)
    assert response.youtube_video_id == "dQw4w9WgXcQ"
    assert response.title == "Rick Astley - Never Gonna Give You Up"
    assert response.channel_name == "Rick Astley"
    assert response.duration == 212
    assert response.added_at == data["added_at"]


def test_channel_list_response_structure():
    """Test ChannelListResponse structure with pagination."""
    channel_id = uuid4()
    channels = [
        ChannelPublicResponse(
            id=channel_id,
            name="python-basics",
            display_title="Python Basics",
            description="Learn Python",
            video_count=10,
            created_at=datetime.now(timezone.utc),
        )
    ]

    response = ChannelListResponse(
        channels=channels,
        total=1,
        limit=50,
        offset=0,
    )

    assert len(response.channels) == 1
    assert response.channels[0].name == "python-basics"
    assert response.total == 1
    assert response.limit == 50
    assert response.offset == 0


def test_channel_video_list_response_structure():
    """Test ChannelVideoListResponse structure with pagination."""
    transcript_id = uuid4()
    videos = [
        VideoInChannelResponse(
            transcript_id=transcript_id,
            youtube_video_id="abc123",
            title="Test Video",
            channel_name="Test Channel",
            duration=180,
            added_at=datetime.now(timezone.utc),
        )
    ]

    response = ChannelVideoListResponse(
        videos=videos,
        total=1,
        limit=50,
        offset=0,
    )

    assert len(response.videos) == 1
    assert response.videos[0].youtube_video_id == "abc123"
    assert response.total == 1
    assert response.limit == 50
    assert response.offset == 0


def test_channel_conversation_response_serialization():
    """Test ChannelConversationResponse serialization."""
    conv_id = uuid4()
    channel_id = uuid4()
    user_id = uuid4()

    data = {
        "id": conv_id,
        "channel_id": channel_id,
        "user_id": user_id,
        "channel_name": "python-tutorials",
        "channel_display_title": "Python Tutorials",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    response = ChannelConversationResponse(**data)

    assert str(response.id) == str(conv_id)
    assert str(response.channel_id) == str(channel_id)
    assert str(response.user_id) == str(user_id)
    assert response.channel_name == "python-tutorials"
    assert response.channel_display_title == "Python Tutorials"
    assert response.created_at == data["created_at"]
    assert response.updated_at == data["updated_at"]


def test_channel_conversation_detail_response_with_messages():
    """Test ChannelConversationDetailResponse with messages."""
    conv_id = uuid4()
    channel_id = uuid4()
    user_id = uuid4()
    message_id = uuid4()

    conversation = ChannelConversationResponse(
        id=conv_id,
        channel_id=channel_id,
        user_id=user_id,
        channel_name="python-tutorials",
        channel_display_title="Python Tutorials",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    messages = [
        MessageResponse(
            id=message_id,
            conversation_id=None,
            channel_conversation_id=conv_id,
            role="user",
            content="What is Python?",
            meta_data={},
            created_at=datetime.now(timezone.utc),
        )
    ]

    response = ChannelConversationDetailResponse(
        conversation=conversation,
        messages=messages,
    )

    assert response.conversation.id == conv_id
    assert len(response.messages) == 1
    assert response.messages[0].content == "What is Python?"
    assert response.messages[0].role == "user"


def test_channel_conversation_list_response_structure():
    """Test ChannelConversationListResponse structure with pagination."""
    conv_id = uuid4()
    channel_id = uuid4()
    user_id = uuid4()

    conversations = [
        ChannelConversationResponse(
            id=conv_id,
            channel_id=channel_id,
            user_id=user_id,
            channel_name="python-tutorials",
            channel_display_title="Python Tutorials",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    ]

    response = ChannelConversationListResponse(
        conversations=conversations,
        total=1,
        limit=50,
        offset=0,
    )

    assert len(response.conversations) == 1
    assert response.conversations[0].channel_name == "python-tutorials"
    assert response.total == 1
    assert response.limit == 50
    assert response.offset == 0


def test_channel_public_response_optional_description():
    """Test ChannelPublicResponse with None description (optional field)."""
    data = {
        "id": uuid4(),
        "name": "python-tutorials",
        "display_title": "Python Tutorials",
        "description": None,  # Optional field
        "video_count": 0,
        "created_at": datetime.now(timezone.utc),
    }

    response = ChannelPublicResponse(**data)

    assert response.description is None
    assert response.video_count == 0
