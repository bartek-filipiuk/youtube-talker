"""
Usage Repository

Database operations for UsageTracking model.
Tracks videos loaded and messages sent per user per billing period.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageTracking


class UsageRepository:
    """Repository for usage tracking database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current_usage(self, user_id: UUID) -> Optional[UsageTracking]:
        """
        Get user's current period usage.

        Returns the usage record for the period that contains the current time.

        Args:
            user_id: User's UUID

        Returns:
            UsageTracking or None if no current period
        """
        now = datetime.now(timezone.utc)

        result = await self.session.execute(
            select(UsageTracking).where(
                UsageTracking.user_id == user_id,
                UsageTracking.period_start <= now,
                UsageTracking.period_end > now,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_current_usage(
        self,
        user_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageTracking:
        """
        Get or create usage record for current billing period.

        If no record exists for the current period, creates one.

        Args:
            user_id: User's UUID
            period_start: Start of billing period
            period_end: End of billing period

        Returns:
            UsageTracking for current period
        """
        # Try to get existing record for this period
        result = await self.session.execute(
            select(UsageTracking).where(
                UsageTracking.user_id == user_id,
                UsageTracking.period_start == period_start,
            )
        )
        usage = result.scalar_one_or_none()

        if usage:
            return usage

        # Create new usage record
        usage = UsageTracking(
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            videos_used=0,
            messages_used=0,
        )
        self.session.add(usage)
        await self.session.flush()
        return usage

    async def increment_videos(self, user_id: UUID) -> Optional[UsageTracking]:
        """
        Increment videos_used count by 1 for current period.

        Args:
            user_id: User's UUID

        Returns:
            Updated UsageTracking or None if no current period
        """
        usage = await self.get_current_usage(user_id)
        if not usage:
            return None

        await self.session.execute(
            update(UsageTracking)
            .where(UsageTracking.id == usage.id)
            .values(
                videos_used=UsageTracking.videos_used + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.session.flush()

        # Refresh to get updated values
        await self.session.refresh(usage)
        return usage

    async def increment_messages(self, user_id: UUID) -> Optional[UsageTracking]:
        """
        Increment messages_used count by 1 for current period.

        Args:
            user_id: User's UUID

        Returns:
            Updated UsageTracking or None if no current period
        """
        usage = await self.get_current_usage(user_id)
        if not usage:
            return None

        await self.session.execute(
            update(UsageTracking)
            .where(UsageTracking.id == usage.id)
            .values(
                messages_used=UsageTracking.messages_used + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.session.flush()

        await self.session.refresh(usage)
        return usage

    async def reset_usage(
        self,
        user_id: UUID,
        new_period_start: datetime,
        new_period_end: datetime,
    ) -> UsageTracking:
        """
        Create a new usage record for a new billing period.

        Called when subscription renews to start fresh usage tracking.

        Args:
            user_id: User's UUID
            new_period_start: Start of new billing period
            new_period_end: End of new billing period

        Returns:
            New UsageTracking record
        """
        usage = UsageTracking(
            user_id=user_id,
            period_start=new_period_start,
            period_end=new_period_end,
            videos_used=0,
            messages_used=0,
        )
        self.session.add(usage)
        await self.session.flush()
        return usage

    async def get_usage_history(
        self,
        user_id: UUID,
        limit: int = 12,
    ) -> list[UsageTracking]:
        """
        Get user's usage history (most recent periods first).

        Args:
            user_id: User's UUID
            limit: Max number of periods to return (default 12 = 1 year)

        Returns:
            List of UsageTracking records
        """
        result = await self.session.execute(
            select(UsageTracking)
            .where(UsageTracking.user_id == user_id)
            .order_by(UsageTracking.period_start.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
