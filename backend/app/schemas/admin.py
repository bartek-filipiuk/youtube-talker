"""
Admin API Schemas

Pydantic models for admin endpoints.
"""

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
