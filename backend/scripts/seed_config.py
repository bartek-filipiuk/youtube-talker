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
from app.db.session import AsyncSessionLocal
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
    async with AsyncSessionLocal() as db:
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
            {
                "key": "registration_enabled",
                "value": {"enabled": True},
                "description": "Allow new user registrations (default: true)"
            },

            # Video Loading Quotas
            {
                "key": "quota.user_video_count_limit",
                "value": {"value": "10", "type": "int"},
                "description": "Max videos per regular user (default: 10)"
            },
            {
                "key": "quota.user_video_duration_limit_seconds",
                "value": {"value": "10800", "type": "int"},
                "description": "Max video duration for regular users in seconds (default: 10800 = 3 hours)"
            },
            {
                "key": "quota.premium_video_duration_limit_seconds",
                "value": {"value": "36000", "type": "int"},
                "description": "Max video duration for premium users in seconds (future: 36000 = 10 hours)"
            },
        ]

        # Upsert config items (set_value handles both create and update)
        for item in config_items:
            await repo.set_value(
                key=item["key"],
                value=item["value"],
                description=item.get("description")
            )
            print(f"✓ Seeded config: {item['key']}")

        # Commit changes
        await db.commit()

    print(f"\n✅ Successfully seeded {len(config_items)} configuration items")


if __name__ == "__main__":
    print("🌱 Seeding configuration table...")
    print("=" * 60)
    asyncio.run(seed_config())
