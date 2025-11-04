"""
Admin API Schemas

Pydantic models for admin endpoints.
"""

from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class AdminStatsResponse(BaseModel):
    """
    Response schema for GET /api/admin/stats

    Contains dashboard statistics for admin panel.
    """

    total_channels: int = Field(
        ..., description="Total number of channels (including soft-deleted)"
    )
    active_channels: int = Field(..., description="Number of active (not deleted) channels")
    total_videos: int = Field(..., description="Total number of videos across all channels")

    class Config:
        from_attributes = True


class UserItem(BaseModel):
    """Single user in admin user list."""

    id: UUID = Field(..., description="User UUID")
    email: str = Field(..., description="User email address")
    role: str = Field(..., description="User role (user | admin)")
    transcript_count: int = Field(..., description="Number of transcripts owned")
    created_at: datetime = Field(..., description="Account creation timestamp")

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """
    Response schema for GET /api/admin/users

    Paginated list of users for admin panel.
    """

    users: List[UserItem] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Items skipped")

    class Config:
        from_attributes = True
