"""
Config Repository

Database operations for Config model.
"""

from typing import Any, Optional, List

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Config
from app.db.repositories.base import BaseRepository


class ConfigRepository(BaseRepository[Config]):
    """Repository for Config model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Config, session)

    async def get_value(self, key: str) -> Optional[Any]:
        """
        Get configuration value by key.

        Args:
            key: Configuration key

        Returns:
            Configuration value or None if not found
        """
        result = await self.session.execute(
            select(Config).where(Config.key == key)
        )
        config = result.scalar_one_or_none()
        return config.value if config else None

    async def set_value(
        self, key: str, value: Any, description: Optional[str] = None
    ) -> Config:
        """
        Set or update configuration value using PostgreSQL UPSERT.

        Thread-safe atomic operation that handles concurrent updates gracefully.
        Uses INSERT ... ON CONFLICT DO UPDATE to avoid race conditions.

        Args:
            key: Configuration key
            value: Configuration value
            description: Optional description

        Returns:
            Config instance
        """
        # Use PostgreSQL UPSERT (INSERT ... ON CONFLICT DO UPDATE)
        # This is atomic and handles concurrent updates without race conditions
        stmt = pg_insert(Config).values(
            key=key,
            value=value,
            description=description
        ).on_conflict_do_update(
            index_elements=['key'],
            set_={
                'value': value,
                'description': description,
                'updated_at': func.now()
            }
        )

        await self.session.execute(stmt)
        await self.session.flush()

        # Fetch and return the config
        result = await self.session.execute(
            select(Config).where(Config.key == key)
        )
        return result.scalar_one()

    async def get_all(self) -> List[Config]:
        """
        Get all configuration items.

        Returns:
            List of all Config instances
        """
        result = await self.session.execute(select(Config))
        return list(result.scalars().all())
