"""
Pydantic Schemas for Channel APIs

Request and response models for channel management endpoints.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# Request Models

class ChannelCreateRequest(BaseModel):
    """Request to create a new channel."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r'^[a-z0-9\-]+$',
        description="URL-safe channel name (lowercase, numbers, hyphens only)"
    )
    display_title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable channel title"
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Channel description (optional)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "python-basics",
                "display_title": "Python Basics",
                "description": "Learn Python fundamentals through curated video content"
            }
        }
    )


class ChannelUpdateRequest(BaseModel):
    """Request to update channel metadata."""

    display_title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Updated channel title"
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Updated channel description"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "display_title": "Python Fundamentals",
                "description": "Updated description with more details"
            }
        }
    )


class VideoToChannelRequest(BaseModel):
    """Request to add video to channel via YouTube URL."""

    youtube_url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Full YouTube video URL"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            }
        }
    )


# Response Models

class ChannelResponse(BaseModel):
    """Full channel details."""

    id: str = Field(..., description="Channel UUID")
    name: str = Field(..., description="URL-safe channel name")
    display_title: str = Field(..., description="Human-readable title")
    description: Optional[str] = Field(None, description="Channel description")
    qdrant_collection_name: str = Field(..., description="Qdrant collection name")
    created_by: Optional[str] = Field(None, description="Creator user UUID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    deleted_at: Optional[datetime] = Field(None, description="Deletion timestamp (soft delete)")
    video_count: int = Field(..., description="Total videos in channel")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "python-basics",
                "display_title": "Python Basics",
                "description": "Learn Python fundamentals",
                "qdrant_collection_name": "channel_python_basics",
                "created_by": "660e8400-e29b-41d4-a716-446655440001",
                "created_at": "2025-11-03T10:00:00Z",
                "updated_at": "2025-11-03T10:00:00Z",
                "deleted_at": None,
                "video_count": 12
            }
        }
    )


class ChannelListItem(BaseModel):
    """Minimal channel info for list views."""

    id: str = Field(..., description="Channel UUID")
    name: str = Field(..., description="URL-safe channel name")
    display_title: str = Field(..., description="Human-readable title")
    created_at: datetime = Field(..., description="Creation timestamp")
    video_count: int = Field(..., description="Total videos in channel")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "python-basics",
                "display_title": "Python Basics",
                "created_at": "2025-11-03T10:00:00Z",
                "video_count": 12
            }
        }
    )


class ChannelListResponse(BaseModel):
    """Paginated channel list."""

    channels: List[ChannelListItem] = Field(..., description="List of channels")
    total: int = Field(..., description="Total channel count")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Number of items skipped")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "channels": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "python-basics",
                        "display_title": "Python Basics",
                        "created_at": "2025-11-03T10:00:00Z",
                        "video_count": 12
                    }
                ],
                "total": 25,
                "limit": 50,
                "offset": 0
            }
        }
    )


class ChannelVideoItem(BaseModel):
    """Video in a channel with metadata."""

    id: str = Field(..., description="ChannelVideo UUID")
    transcript_id: str = Field(..., description="Transcript UUID")
    youtube_video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    channel_name: str = Field(..., description="YouTube channel name")
    duration: int = Field(..., description="Video duration in seconds")
    added_by: Optional[str] = Field(None, description="User UUID who added this video")
    added_at: datetime = Field(..., description="When video was added to channel")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440002",
                "transcript_id": "880e8400-e29b-41d4-a716-446655440003",
                "youtube_video_id": "dQw4w9WgXcQ",
                "title": "Python Tutorial for Beginners",
                "channel_name": "Tech Academy",
                "duration": 1800,
                "added_by": "660e8400-e29b-41d4-a716-446655440001",
                "added_at": "2025-11-03T11:00:00Z"
            }
        }
    )


class ChannelVideoListResponse(BaseModel):
    """Paginated channel video list."""

    videos: List[ChannelVideoItem] = Field(..., description="List of videos")
    total: int = Field(..., description="Total video count")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Number of items skipped")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "videos": [
                    {
                        "id": "770e8400-e29b-41d4-a716-446655440002",
                        "transcript_id": "880e8400-e29b-41d4-a716-446655440003",
                        "youtube_video_id": "dQw4w9WgXcQ",
                        "title": "Python Tutorial for Beginners",
                        "channel_name": "Tech Academy",
                        "duration": 1800,
                        "added_by": "660e8400-e29b-41d4-a716-446655440001",
                        "added_at": "2025-11-03T11:00:00Z"
                    }
                ],
                "total": 12,
                "limit": 50,
                "offset": 0
            }
        }
    )
