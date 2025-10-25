"""
Config Service

Provides access to configuration values stored in the database.
Uses in-memory caching for performance.
"""

from loguru import logger
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.config_repo import ConfigRepository



class ConfigService:
    """
    Configuration service with in-memory caching.

    Loads configuration from the database config table and caches values
    in memory for fast access. Provides type parsing for common value types.

    Example Usage:
        config_service = ConfigService(db)
        max_messages = await config_service.get_config("rag.context_messages", default=10)
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize config service.

        Args:
            db: Database session for loading config values
        """
        self.db = db
        self._cache: Dict[str, Any] = {}
        self._cache_loaded = False

    async def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key with type parsing.

        Loads cache on first access. Returns cached value if available,
        otherwise returns default value.

        Type parsing:
            - "true", "1", "yes" → True
            - "false", "0", "no" → False
            - Numeric strings → int or float
            - Everything else → str

        Args:
            key: Configuration key (e.g., "rag.top_k")
            default: Default value if key not found (default: None)

        Returns:
            Configuration value with appropriate type, or default if not found

        Example:
            >>> await config_service.get_config("rag.top_k", default=12)
            12
        """
        # Load cache if not already loaded
        if not self._cache_loaded:
            await self._load_cache()

        # Return cached value or default
        return self._cache.get(key, default)

    async def _load_cache(self) -> None:
        """
        Load all configuration values from database into cache.

        Queries the config table and stores all key-value pairs in memory.
        Values are parsed from JSONB format and converted to appropriate types.

        Called automatically on first get_config() call.
        """
        repo = ConfigRepository(self.db)
        config_items = await repo.get_all()

        for item in config_items:
            # Extract value and type from JSONB
            # Expected format: {"value": "...", "type": "str|int|float|bool"}
            value_data = item.value

            if isinstance(value_data, dict) and "value" in value_data:
                raw_value = value_data["value"]
                value_type = value_data.get("type", "str")
                parsed_value = self._parse_value(raw_value, value_type)
                self._cache[item.key] = parsed_value
            else:
                # Fallback: treat entire JSONB as value
                self._cache[item.key] = value_data

        self._cache_loaded = True
        logger.info(f"Loaded {len(self._cache)} configuration values from database")

    def _parse_value(self, value: str, value_type: str) -> Any:
        """
        Parse string value to appropriate Python type.

        Args:
            value: String value from database
            value_type: Type hint ("int", "float", "bool", or "str")

        Returns:
            Parsed value with correct type

        Example:
            >>> self._parse_value("12", "int")
            12
            >>> self._parse_value("true", "bool")
            True
        """
        if value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        else:
            return value

    async def refresh(self) -> None:
        """
        Reload configuration from database.

        Clears the cache and reloads all config values.
        Useful for picking up configuration changes without restarting the server.

        Example:
            >>> await config_service.refresh()
        """
        self._cache.clear()
        self._cache_loaded = False
        await self._load_cache()
        logger.info("Configuration cache refreshed")

    def get_cached_value(self, key: str) -> Optional[Any]:
        """
        Get value from cache without database access.

        Returns None if cache not loaded or key not found.
        Useful for testing or when you know the cache is loaded.

        Args:
            key: Configuration key

        Returns:
            Cached value or None if not found

        Example:
            >>> config_service.get_cached_value("rag.top_k")
            12
        """
        return self._cache.get(key)
