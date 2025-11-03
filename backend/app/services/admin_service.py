"""
Admin Service

Business logic for admin dashboard and statistics.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Channel, ChannelVideo


class AdminService:
    """
    Admin service for dashboard statistics.

    Provides aggregate statistics across channels and videos.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize admin service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_stats(self) -> dict:
        """
        Get admin dashboard statistics.

        Returns counts for:
        - Total channels (all)
        - Active channels (is_active=True)
        - Total videos across all channels

        Returns:
            dict: Statistics with keys:
                - total_channels: int
                - active_channels: int
                - total_videos: int
        """
        # Count total channels
        total_channels_result = await self.db.execute(select(func.count(Channel.id)))
        total_channels = total_channels_result.scalar() or 0

        # Count active channels (is_active=True)
        active_channels_result = await self.db.execute(
            select(func.count(Channel.id)).where(Channel.is_active == True)  # noqa: E712
        )
        active_channels = active_channels_result.scalar() or 0

        # Count total videos across all channels
        total_videos_result = await self.db.execute(select(func.count(ChannelVideo.id)))
        total_videos = total_videos_result.scalar() or 0

        return {
            "total_channels": total_channels,
            "active_channels": active_channels,
            "total_videos": total_videos,
        }
