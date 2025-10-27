"""
User Repository

Database operations for User model.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
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
        Increment the transcript_count for a user.

        This method is called after successfully ingesting a new transcript.
        Used for quota enforcement (e.g., max 10 videos for regular users).

        Args:
            user_id: UUID of the user

        Raises:
            ValueError: If user not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        user.transcript_count += 1
        await self.session.commit()
        await self.session.refresh(user)
