"""
Unit Tests for Channel Pydantic Schemas

Tests for request and response model validation.
"""

import pytest
from pydantic import ValidationError

from app.schemas.channel import (
    ChannelCreateRequest,
    ChannelUpdateRequest,
    VideoToChannelRequest,
    ChannelResponse,
    ChannelListItem,
)


def test_channel_create_request_valid():
    """Test ChannelCreateRequest with valid data."""
    data = {
        "name": "python-basics",
        "display_title": "Python Basics",
        "description": "Learn Python"
    }
    request = ChannelCreateRequest(**data)

    assert request.name == "python-basics"
    assert request.display_title == "Python Basics"
    assert request.description == "Learn Python"


def test_channel_create_request_invalid_name_uppercase():
    """Test ChannelCreateRequest rejects uppercase in name."""
    data = {
        "name": "Python-Basics",  # Invalid - has uppercase
        "display_title": "Python Basics"
    }

    with pytest.raises(ValidationError) as exc_info:
        ChannelCreateRequest(**data)

    assert "name" in str(exc_info.value)


def test_channel_create_request_invalid_name_special_chars():
    """Test ChannelCreateRequest rejects special characters."""
    data = {
        "name": "python_basics",  # Invalid - has underscore
        "display_title": "Python Basics"
    }

    with pytest.raises(ValidationError) as exc_info:
        ChannelCreateRequest(**data)

    assert "name" in str(exc_info.value)


def test_channel_create_request_valid_name_patterns():
    """Test ChannelCreateRequest accepts valid name patterns."""
    valid_names = ["python", "python-basics", "python-basics-101", "abc123"]

    for name in valid_names:
        request = ChannelCreateRequest(name=name, display_title="Title")
        assert request.name == name


def test_channel_create_request_minimal():
    """Test ChannelCreateRequest with minimal fields."""
    request = ChannelCreateRequest(
        name="minimal",
        display_title="Minimal Channel"
    )

    assert request.name == "minimal"
    assert request.display_title == "Minimal Channel"
    assert request.description is None


def test_channel_update_request_optional_fields():
    """Test ChannelUpdateRequest with optional fields."""
    # Empty update
    request1 = ChannelUpdateRequest()
    assert request1.display_title is None
    assert request1.description is None

    # Partial update
    request2 = ChannelUpdateRequest(display_title="Updated Title")
    assert request2.display_title == "Updated Title"
    assert request2.description is None


def test_video_to_channel_request_valid():
    """Test VideoToChannelRequest with valid YouTube URL."""
    request = VideoToChannelRequest(
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    assert "youtube.com" in request.youtube_url


def test_video_to_channel_request_requires_url():
    """Test VideoToChannelRequest requires youtube_url."""
    with pytest.raises(ValidationError) as exc_info:
        VideoToChannelRequest()

    assert "youtube_url" in str(exc_info.value)


def test_channel_response_serialization():
    """Test ChannelResponse can serialize from model-like dict."""
    from datetime import datetime, timezone

    data = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "python-basics",
        "display_title": "Python Basics",
        "description": "Learn Python",
        "qdrant_collection_name": "channel_python_basics",
        "created_by": "660e8400-e29b-41d4-a716-446655440001",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
        "video_count": 12
    }

    response = ChannelResponse(**data)
    assert response.id == data["id"]
    assert response.name == data["name"]
    assert response.video_count == 12


def test_channel_list_item_from_attributes():
    """Test ChannelListItem can be created from attributes."""
    from datetime import datetime, timezone

    data = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "python-basics",
        "display_title": "Python Basics",
        "created_at": datetime.now(timezone.utc),
        "video_count": 5
    }

    item = ChannelListItem(**data)
    assert item.video_count == 5
    assert item.name == "python-basics"
