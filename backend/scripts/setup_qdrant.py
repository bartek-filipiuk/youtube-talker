"""Setup script to create Qdrant collection for youtube_chunks."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.qdrant_service import QdrantService


async def main():
    """Create Qdrant collection if it doesn't exist."""
    print("Setting up Qdrant collection...")

    service = QdrantService()

    try:
        await service.create_collection()

        print("✓ Qdrant collection 'youtube_chunks' created successfully")
        print("  - Vector size: 1536")
        print("  - Distance: Cosine")
        print("  - Indexes: user_id, youtube_video_id")

        # Verify health
        healthy = await service.health_check()
        if healthy:
            print("✓ Qdrant connection verified")
        else:
            print("⚠ Qdrant health check failed")

    except Exception as e:
        print(f"✗ Error setting up Qdrant: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
