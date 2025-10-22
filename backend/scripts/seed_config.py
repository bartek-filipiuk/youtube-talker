"""
Seed Configuration Script

Populates the config table with default configuration values.
Run this script after database migrations to initialize system config.

Usage:
    python scripts/seed_config.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_async_sessionmaker
from app.db.repositories.config_repo import ConfigRepository


async def seed_config():
    """
    Seed the config table with default values.

    Configuration items follow this structure:
    - key: Configuration key (e.g., "rag.top_k")
    - value: JSONB with {"value": "...", "type": "int|float|bool|str"}
    - description: Human-readable description

    For MVP, these values mirror hardcoded settings in app.config.
    This provides visibility and foundation for future dynamic configuration.
    """

    # Create async session
    sessionmaker = get_async_sessionmaker()
    async with sessionmaker() as db:
        repo = ConfigRepository(db)

        # Define configuration items
        config_items = [
            # RAG Configuration
            {
                "key": "rag.top_k",
                "value": {"value": "12", "type": "int"},
                "description": "Number of chunks to retrieve for RAG context (default: 12)"
            },
            {
                "key": "rag.context_messages",
                "value": {"value": "10", "type": "int"},
                "description": "Number of conversation messages to include in context (default: 10)"
            },
            {
                "key": "rag.chunk_size",
                "value": {"value": "700", "type": "int"},
                "description": "Chunk size in tokens for transcript splitting (default: 700)"
            },
            {
                "key": "rag.chunk_overlap_percent",
                "value": {"value": "20", "type": "int"},
                "description": "Percentage overlap between chunks (default: 20%)"
            },

            # Rate Limiting
            {
                "key": "rate_limit.websocket_messages_per_minute",
                "value": {"value": "10", "type": "int"},
                "description": "Max WebSocket messages per user per minute (default: 10)"
            },
            {
                "key": "rate_limit.api_requests_per_minute",
                "value": {"value": "60", "type": "int"},
                "description": "Max API requests per IP per minute (default: 60)"
            },

            # Authentication
            {
                "key": "auth.session_expires_days",
                "value": {"value": "7", "type": "int"},
                "description": "Session expiry in days (default: 7)"
            },

            # Feature Flags
            {
                "key": "feature.langsmith_enabled",
                "value": {"value": "false", "type": "bool"},
                "description": "Enable LangSmith tracing (default: false)"
            },
        ]

        # Upsert config items
        for item in config_items:
            existing = await repo.get_by_key(item["key"])

            if existing:
                # Update existing item
                await repo.update(
                    key=item["key"],
                    value=item["value"],
                    description=item.get("description")
                )
                print(f"✓ Updated config: {item['key']}")
            else:
                # Create new item
                await repo.create(
                    key=item["key"],
                    value=item["value"],
                    description=item.get("description")
                )
                print(f"✓ Created config: {item['key']}")

        # Commit changes
        await db.commit()

    print(f"\n✅ Successfully seeded {len(config_items)} configuration items")


if __name__ == "__main__":
    print("🌱 Seeding configuration table...")
    print("=" * 60)
    asyncio.run(seed_config())
