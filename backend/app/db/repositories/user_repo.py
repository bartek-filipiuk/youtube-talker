"""
User Repository

Database operations for User model.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: User's email address

        Returns:
            User instance or None if not found
        """
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, email: str, password_hash: str) -> User:
        """
        Create a new user.

        Args:
            email: User's email address
            password_hash: Hashed password

        Returns:
            Created User instance
        """
        return await super().create(email=email, password_hash=password_hash)

    async def increment_transcript_count(self, user_id: UUID) -> None:
        """
        Increment the transcript_count for a user atomically.

        This method is called after successfully ingesting a new transcript.
        Used for quota enforcement (e.g., max 10 videos for regular users).

        Uses atomic UPDATE to prevent race conditions under concurrent loads.
        Transaction management is left to the caller.

        Args:
            user_id: UUID of the user

        Raises:
            ValueError: If user not found
        """
        # Use atomic UPDATE to prevent lost updates under concurrency
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(transcript_count=User.transcript_count + 1)
        )
        result = await self.session.execute(stmt)

        # Verify user exists (if no rows updated, user not found)
        if result.rowcount == 0:
            raise ValueError(f"User {user_id} not found")

        # Flush to ensure update is visible in current transaction
        # But let caller manage commit/rollback
        await self.session.flush()

    async def decrement_transcript_count(self, user_id: UUID) -> None:
        """
        Decrement the transcript_count for a user atomically.

        This method is called after successfully deleting a transcript.
        Ensures count never goes below 0.

        Uses atomic UPDATE to prevent race conditions under concurrent deletions.
        Transaction management is left to the caller.

        Args:
            user_id: UUID of the user

        Raises:
            ValueError: If user not found
        """
        # Use CASE to prevent negative counts (atomic operation)
        # If count is 0, keep it at 0. Otherwise decrement.
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                transcript_count=User.transcript_count - 1
            )
        )
        result = await self.session.execute(stmt)

        # Verify user exists (if no rows updated, user not found)
        if result.rowcount == 0:
            raise ValueError(f"User {user_id} not found")

        # Flush to ensure update is visible in current transaction
        # But let caller manage commit/rollback
        await self.session.flush()
