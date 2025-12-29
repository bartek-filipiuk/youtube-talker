"""
Usage Service

Provides usage limit checking and enforcement for videos and messages.
Used by transcript ingestion and chat handlers to enforce subscription limits.
"""

from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UsageLimitExceededError
from app.services.billing_service import BillingService


class UsageService:
    """
    Service for checking and enforcing usage limits.

    Provides:
    - Video limit checking before ingestion
    - Message limit checking before chat
    - Usage increment after successful operations
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize usage service.

        Args:
            db: SQLAlchemy async session
        """
        self.db = db
        self.billing_service = BillingService(db)

    async def check_can_load_video(self, user_id: UUID) -> tuple[bool, int, Optional[int]]:
        """
        Check if user can load another video.

        Args:
            user_id: User's UUID

        Returns:
            Tuple of (can_load, videos_used, video_limit)
            video_limit is None if unlimited
        """
        return await self.billing_service.check_video_limit(user_id)

    async def check_can_send_message(self, user_id: UUID) -> tuple[bool, int, Optional[int]]:
        """
        Check if user can send another message.

        Args:
            user_id: User's UUID

        Returns:
            Tuple of (can_send, messages_used, message_limit)
            message_limit is None if unlimited
        """
        return await self.billing_service.check_message_limit(user_id)

    async def enforce_video_limit(self, user_id: UUID) -> None:
        """
        Enforce video limit - raise exception if exceeded.

        Call this BEFORE video ingestion.

        Args:
            user_id: User's UUID

        Raises:
            UsageLimitExceededError: If video limit is exceeded
        """
        can_load, used, limit = await self.check_can_load_video(user_id)

        if not can_load:
            logger.warning(f"User {user_id} exceeded video limit: {used}/{limit}")
            raise UsageLimitExceededError(
                limit_type="video",
                used=used,
                limit=limit,
                message=f"Video limit exceeded. You've used {used} of {limit} videos this month. Upgrade to Pro for more.",
            )

    async def enforce_message_limit(self, user_id: UUID) -> None:
        """
        Enforce message limit - raise exception if exceeded.

        Call this BEFORE sending a message.

        Args:
            user_id: User's UUID

        Raises:
            UsageLimitExceededError: If message limit is exceeded
        """
        can_send, used, limit = await self.check_can_send_message(user_id)

        if not can_send:
            logger.warning(f"User {user_id} exceeded message limit: {used}/{limit}")
            raise UsageLimitExceededError(
                limit_type="message",
                used=used,
                limit=limit,
                message=f"Message limit exceeded. You've used {used} of {limit} messages this month. Upgrade to Pro for more.",
            )

    async def record_video_usage(self, user_id: UUID) -> None:
        """
        Record successful video load.

        Call this AFTER successful video ingestion.

        Args:
            user_id: User's UUID
        """
        await self.billing_service.increment_video_usage(user_id)
        logger.debug(f"Incremented video usage for user {user_id}")

    async def record_message_usage(self, user_id: UUID) -> None:
        """
        Record successful message send.

        Call this AFTER successful message processing.

        Args:
            user_id: User's UUID
        """
        await self.billing_service.increment_message_usage(user_id)
        logger.debug(f"Incremented message usage for user {user_id}")
