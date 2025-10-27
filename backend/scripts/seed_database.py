"""Seed database with test data for development.

Creates test users and ingests sample YouTube transcripts.
Idempotent - skips existing data and only creates missing data.

Usage:
    python scripts/seed_database.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.transcript_repo import TranscriptRepository
from app.db.repositories.user_repo import UserRepository
from app.db.session import async_session_maker
from app.services.auth_service import AuthService
from app.services.transcript_service import TranscriptService

# Test data configuration
TEST_USERS = [
    {
        "email": "test@example.com",
        "password": "testpass123",
        "name": "Test User",
    },
    {
        "email": "demo@example.com",
        "password": "demopass123",
        "name": "Demo User",
    },
]

# Sample YouTube videos to ingest (short educational videos)
SAMPLE_VIDEOS = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Example video 1
    "https://www.youtube.com/watch?v=jNQXAC9IVRw",  # Example video 2
]


async def create_test_users(db: AsyncSession) -> list:
    """
    Create test users if they don't exist.

    Args:
        db: Database session

    Returns:
        List of created/existing user IDs
    """
    print("\n" + "=" * 60)
    print("CREATING TEST USERS")
    print("=" * 60)

    user_repo = UserRepository(db)
    created_users = []

    for idx, user_data in enumerate(TEST_USERS):
        print(f"\nProcessing user: {user_data['email']}")

        # Check if user already exists
        existing_user = await user_repo.get_by_email(user_data["email"])

        if existing_user:
            print(f"  ⏭ User already exists, skipping (id={existing_user.id})")
            # Make first user admin if not already
            if idx == 0 and existing_user.role != "admin":
                existing_user.role = "admin"
                await db.commit()
                print("  ✓ Updated to admin role")
            created_users.append(existing_user)
        else:
            # Create new user
            auth_service = AuthService(db)
            try:
                new_user = await auth_service.register_user(
                    email=user_data["email"],
                    password=user_data["password"],
                )
                # Make first user admin
                if idx == 0:
                    new_user.role = "admin"
                await db.commit()
                role_label = " (admin)" if idx == 0 else ""
                print(f"  ✓ Created user{role_label} (id={new_user.id})")
                created_users.append(new_user)
            except Exception as e:
                await db.rollback()
                print(f"  ✗ Failed to create user: {e}")
                continue

    print(f"\n✓ Users ready: {len(created_users)}/{len(TEST_USERS)}")
    return created_users


async def ingest_sample_transcripts(db: AsyncSession, users: list) -> None:
    """
    Ingest sample YouTube transcripts for test users.

    Args:
        db: Database session
        users: List of user objects to ingest transcripts for
    """
    print("\n" + "=" * 60)
    print("INGESTING SAMPLE TRANSCRIPTS")
    print("=" * 60)

    if not users:
        print("⚠ No users available for transcript ingestion")
        return

    # Use first test user for sample transcripts
    test_user = users[0]
    print(f"\nIngesting transcripts for user: {test_user.email} (id={test_user.id})")

    transcript_service = TranscriptService()
    transcript_repo = TranscriptRepository(db)

    ingested_count = 0
    skipped_count = 0

    for video_url in SAMPLE_VIDEOS:
        print(f"\nProcessing video: {video_url}")

        try:
            # Extract video ID to check for duplicate
            video_id = transcript_service._extract_video_id(video_url)

            # Check if transcript already exists
            existing = await transcript_repo.get_by_video_id(test_user.id, video_id)

            if existing:
                print(f"  ⏭ Transcript already exists, skipping (id={existing.id})")
                skipped_count += 1
                continue

            # Ingest new transcript
            print("  📥 Fetching and ingesting transcript...")
            result = await transcript_service.ingest_transcript(
                youtube_url=video_url,
                user_id=test_user.id,
                db_session=db,
            )

            print("  ✓ Ingested successfully!")
            print(f"    - Transcript ID: {result['transcript_id']}")
            print(f"    - Video ID: {result['youtube_video_id']}")
            print(f"    - Chunks created: {result['chunk_count']}")
            ingested_count += 1

        except ValueError as e:
            # Expected error (e.g., duplicate)
            print(f"  ⏭ Skipped: {e}")
            skipped_count += 1
        except Exception as e:
            # Unexpected error
            print(f"  ✗ Failed to ingest: {e}")
            continue

    print("\n✓ Transcripts processed:")
    print(f"  - Ingested: {ingested_count}")
    print(f"  - Skipped (existing): {skipped_count}")


async def main():
    """Run database seeding."""
    print("\n" + "=" * 60)
    print("DATABASE SEEDING SCRIPT")
    print("=" * 60)
    print("\nThis script will create test data for development.")
    print("It is idempotent - existing data will be skipped.\n")

    try:
        # Create database session
        async with async_session_maker() as db:
            # Step 1: Create test users
            users = await create_test_users(db)

            # Step 2: Ingest sample transcripts
            await ingest_sample_transcripts(db, users)

        print("\n" + "=" * 60)
        print("✓✓✓ DATABASE SEEDING COMPLETE ✓✓✓")
        print("=" * 60)
        print("\nTest users created:")
        for user_data in TEST_USERS:
            print(f"  - {user_data['email']} / {user_data['password']}")
        print("\nYou can now use these credentials for testing!")

    except Exception as e:
        print(f"\n✗ SEEDING FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
