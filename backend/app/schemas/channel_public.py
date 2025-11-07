"""
Channel Public API Schemas

Pydantic models for user-facing channel discovery and conversation APIs.
These schemas provide safe, public-facing views excluding admin-only fields.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.schemas.conversation import MessageResponse


class ChannelPublicResponse(BaseModel):
    """
    Public-safe channel metadata response.

    Excludes admin fields like created_by and qdrant_collection_name.
    Used in channel discovery endpoints.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "python-tutorials",
                "display_title": "Python Tutorials",
                "description": "Learn Python programming from basics to advanced",
                "video_count": 42,
                "created_at": "2025-01-15T10:30:00Z",
            }
        },
    )

    id: UUID = Field(description="Channel UUID")
    name: str = Field(description="URL-safe channel name (lowercase, hyphens)")
    display_title: str = Field(description="Human-readable channel title")
    description: Optional[str] = Field(None, description="Channel description (optional)")
    video_count: int = Field(description="Total number of videos in channel")
    created_at: datetime = Field(description="Channel creation timestamp")


class VideoInChannelResponse(BaseModel):
    """
    Public-safe video metadata for videos in a channel.

    Used in channel video list endpoints.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "transcript_id": "650e8400-e29b-41d4-a716-446655440001",
                "youtube_video_id": "dQw4w9WgXcQ",
                "title": "Python Basics - Variables and Data Types",
                "channel_name": "Python Tutorials",
                "duration": 1234,
                "added_at": "2025-01-15T10:30:00Z",
            }
        },
    )

    transcript_id: UUID = Field(description="Transcript UUID (internal)")
    youtube_video_id: str = Field(description="YouTube video ID")
    title: str = Field(description="Video title")
    channel_name: str = Field(description="YouTube channel name")
    duration: Optional[int] = Field(None, description="Video duration in seconds")
    added_at: datetime = Field(description="Timestamp when video was added to channel")


class ChannelVideoListResponse(BaseModel):
    """
    Paginated list of videos in a channel.

    Used in GET /api/channels/{id}/videos endpoint.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "videos": [],
                "total": 42,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    videos: List[VideoInChannelResponse] = Field(
        default_factory=list,
        description="List of videos (newest first)",
    )
    total: int = Field(description="Total number of videos returned")
    limit: int = Field(description="Pagination limit used")
    offset: int = Field(description="Pagination offset used")


class ChannelListResponse(BaseModel):
    """
    Paginated list of channels.

    Used in GET /api/channels endpoint.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "channels": [],
                "total": 10,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    channels: List[ChannelPublicResponse] = Field(
        default_factory=list,
        description="List of active channels",
    )
    total: int = Field(description="Total number of channels returned")
    limit: int = Field(description="Pagination limit used")
    offset: int = Field(description="Pagination offset used")


class ChannelConversationResponse(BaseModel):
    """
    Channel conversation metadata response.

    Represents a user's personal conversation with a channel.
    Each user has separate conversations with each channel.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "750e8400-e29b-41d4-a716-446655440002",
                "channel_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "850e8400-e29b-41d4-a716-446655440003",
                "channel_name": "python-tutorials",
                "channel_display_title": "Python Tutorials",
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T14:45:00Z",
            }
        },
    )

    id: UUID = Field(description="Channel conversation UUID")
    channel_id: UUID = Field(description="Parent channel UUID")
    user_id: UUID = Field(description="Owner user UUID")
    model: str = Field(description="LLM model used for this conversation")
    channel_name: str = Field(description="Channel URL-safe name")
    channel_display_title: str = Field(description="Channel display title")
    created_at: datetime = Field(description="Conversation creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ChannelConversationDetailResponse(BaseModel):
    """
    Full channel conversation with messages.

    Used in GET /api/channels/conversations/{id} endpoint.
    Includes conversation metadata plus all messages in chronological order.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "conversation": {
                    "id": "750e8400-e29b-41d4-a716-446655440002",
                    "channel_id": "550e8400-e29b-41d4-a716-446655440000",
                    "user_id": "850e8400-e29b-41d4-a716-446655440003",
                    "channel_name": "python-tutorials",
                    "channel_display_title": "Python Tutorials",
                    "created_at": "2025-01-15T10:30:00Z",
                    "updated_at": "2025-01-15T14:45:00Z",
                },
                "messages": [],
            }
        }
    )

    conversation: ChannelConversationResponse = Field(description="Conversation metadata")
    messages: List[MessageResponse] = Field(
        default_factory=list,
        description="List of messages in chronological order",
    )


class ChannelConversationListResponse(BaseModel):
    """
    Paginated list of user's channel conversations.

    Used in GET /api/channels/conversations endpoint.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "conversations": [],
                "total": 5,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    conversations: List[ChannelConversationResponse] = Field(
        default_factory=list,
        description="List of channel conversations (most recent first)",
    )
    total: int = Field(description="Total number of conversations returned")
    limit: int = Field(description="Pagination limit used")
    offset: int = Field(description="Pagination offset used")
