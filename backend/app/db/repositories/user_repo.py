"""
User Repository

Database operations for User model.
"""

from typing import Optional, Tuple, List
from uuid import UUID

from sqlalchemy import select, update, func
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
        # Use func.greatest to prevent negative counts (atomic operation)
        # If count is 0, keep it at 0. Otherwise decrement.
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                transcript_count=func.greatest(User.transcript_count - 1, 0)
            )
        )
        result = await self.session.execute(stmt)

        # Verify user exists (if no rows updated, user not found)
        if result.rowcount == 0:
            raise ValueError(f"User {user_id} not found")

        # Flush to ensure update is visible in current transaction
        # But let caller manage commit/rollback
        await self.session.flush()

    async def list_all_users(
        self, limit: int = 50, offset: int = 0
    ) -> Tuple[List[User], int]:
        """
        List all users with pagination (admin only).

        Args:
            limit: Maximum number of users to return (default: 50)
            offset: Number of users to skip (default: 0)

        Returns:
            Tuple of (users list, total count)
        """
        # Get total count
        count_stmt = select(func.count()).select_from(User)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        # Get paginated users ordered by created_at DESC (newest first)
        users_stmt = (
            select(User)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        users_result = await self.session.execute(users_stmt)
        users = list(users_result.scalars().all())

        return users, total

    async def delete_user(self, user_id: UUID) -> None:
        """
        Delete user and all related data (admin only).

        Hard delete with manual cascade handling for relationships.
        Deletes: sessions, chunks, transcripts, conversations + messages, channel_conversations + messages

        Args:
            user_id: UUID of user to delete

        Raises:
            ValueError: If user not found
        """
        from app.db.models import Session, Chunk, Transcript, Conversation, ChannelConversation
        from sqlalchemy import delete

        # Get user first to verify exists
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Delete related records manually (order matters for FK constraints)
        # 1. Delete chunks (has RESTRICT constraint on user_id)
        await self.session.execute(delete(Chunk).where(Chunk.user_id == user_id))

        # 2. Delete transcripts (will CASCADE delete remaining chunks via transcript_id)
        await self.session.execute(delete(Transcript).where(Transcript.user_id == user_id))

        # 3. Delete conversations (will CASCADE delete messages)
        await self.session.execute(delete(Conversation).where(Conversation.user_id == user_id))

        # 4. Delete channel conversations (will CASCADE delete messages)
        await self.session.execute(delete(ChannelConversation).where(ChannelConversation.user_id == user_id))

        # 5. Delete sessions
        await self.session.execute(delete(Session).where(Session.user_id == user_id))

        # 6. Finally delete user
        await self.session.delete(user)
        await self.session.flush()

    async def update_password(self, user_id: UUID, new_password_hash: str) -> None:
        """
        Update user's password hash.

        Args:
            user_id: UUID of the user
            new_password_hash: New bcrypt password hash

        Raises:
            ValueError: If user not found
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(password_hash=new_password_hash)
        )
        result = await self.session.execute(stmt)

        if result.rowcount == 0:
            raise ValueError(f"User {user_id} not found")

        await self.session.flush()
