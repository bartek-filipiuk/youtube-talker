"""
Config Repository

Database operations for Config model.
"""

from typing import Any, Optional, List

from sqlalchemy import select
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
        Set or update configuration value.

        Args:
            key: Configuration key
            value: Configuration value
            description: Optional description

        Returns:
            Config instance
        """
        # Check if exists
        result = await self.session.execute(
            select(Config).where(Config.key == key)
        )
        config = result.scalar_one_or_none()

        if config:
            # Update existing
            config.value = value
            if description:
                config.description = description
            await self.session.flush()
            await self.session.refresh(config)
            return config
        else:
            # Create new
            config = Config(key=key, value=value, description=description)
            self.session.add(config)
            await self.session.flush()
            await self.session.refresh(config)
            return config

    async def get_all(self) -> List[Config]:
        """
        Get all configuration items.

        Returns:
            List of all Config instances
        """
        result = await self.session.execute(select(Config))
        return list(result.scalars().all())
