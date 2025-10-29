"""
Session Repository

Database operations for Session model.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Session
from app.db.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    """Repository for Session model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Session, session)

    async def create(self, user_id: UUID, token_hash: str, expires_at: datetime) -> Session:
        """
        Create a new session.

        Args:
            user_id: User's UUID
            token_hash: Hashed session token
            expires_at: Expiration timestamp

        Returns:
            Created Session instance
        """
        return await super().create(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )

    async def get_by_token(self, token_hash: str) -> Optional[Session]:
        """
        Get session by token hash.

        Args:
            token_hash: Hashed session token

        Returns:
            Session instance or None if not found
        """
        result = await self.session.execute(
            select(Session).where(Session.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def delete_expired(self) -> int:
        """
        Delete all expired sessions.

        Returns:
            Number of sessions deleted
        """
        result = await self.session.execute(
            delete(Session).where(Session.expires_at < datetime.now(timezone.utc))
        )
        await self.session.flush()
        return result.rowcount
