"""Pydantic schemas for transcript API endpoints."""

import re
from datetime import datetime
from typing import Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class TranscriptIngestRequest(BaseModel):
    """Request schema for transcript ingestion."""

    youtube_url: str = Field(
        ...,
        description="YouTube video URL (youtube.com or youtu.be format)",
        examples=[
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
        ],
    )

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Validate YouTube URL format."""
        patterns = [
            r"(?:youtube\.com\/watch\?v=)([\w-]+)",
            r"(?:youtu\.be\/)([\w-]+)",
        ]

        if not any(re.search(p, v) for p in patterns):
            raise ValueError(
                "Invalid YouTube URL format. "
                "Expected: youtube.com/watch?v=ID or youtu.be/ID"
            )

        return v


class TranscriptResponse(BaseModel):
    """Response schema for successful ingestion."""

    id: str = Field(..., description="Transcript database ID (UUID)")
    youtube_video_id: str = Field(
        ..., description="YouTube video ID extracted from URL"
    )
    chunk_count: int = Field(..., description="Number of chunks created")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Video metadata from SUPADATA"
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "youtube_video_id": "dQw4w9WgXcQ",
                "chunk_count": 12,
                "metadata": {
                    "title": "Rick Astley - Never Gonna Give You Up",
                    "duration": 213,
                    "language": "en",
                },
            }
        }


class VideoListItem(BaseModel):
    """Lightweight schema for video list display."""

    id: str = Field(..., description="Transcript database ID (UUID)")
    title: str = Field(..., description="Video title from metadata")
    created_at: datetime = Field(..., description="Transcript creation timestamp")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Rick Astley - Never Gonna Give You Up",
                "created_at": "2025-11-01T10:30:00Z",
            }
        }


class VideoListResponse(BaseModel):
    """Paginated video list response."""

    videos: List[VideoListItem] = Field(..., description="List of videos")
    total: int = Field(..., description="Total number of videos for user")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Current offset")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "videos": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "Rick Astley - Never Gonna Give You Up",
                        "created_at": "2025-11-01T10:30:00Z",
                    }
                ],
                "total": 15,
                "limit": 10,
                "offset": 0,
            }
        }
