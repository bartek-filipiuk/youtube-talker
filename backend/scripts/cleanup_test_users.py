"""
Database Cleanup Script - Remove Test Users

Deletes all test users from the database, keeping only:
- admin@example.com (admin account)
- video_test@example.com (production test account)

Cascade deletes will automatically remove:
- User sessions
- Conversations and messages
- Transcripts and chunks
- Channel conversations
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import AsyncSessionLocal
from app.db.models import User, Chunk, Transcript, Conversation, Session


# Users to KEEP (will NOT be deleted)
PROTECTED_EMAILS = [
    "admin@example.com",
    "video_test@example.com",
]


async def cleanup_test_users():
    """
    Delete all test users except protected accounts.

    Returns:
        int: Number of users deleted
    """
    async with AsyncSessionLocal() as session:
        # Get all users EXCEPT protected ones
        stmt = select(User).where(User.email.notin_(PROTECTED_EMAILS))
        result = await session.execute(stmt)
        users_to_delete = list(result.scalars().all())

        if not users_to_delete:
            logger.info("No test users to delete")
            return 0

        # Log users to be deleted
        logger.info(f"Found {len(users_to_delete)} test users to delete:")
        for user in users_to_delete:
            logger.info(f"  - {user.email} (role: {user.role}, id: {user.id})")

        # Confirm deletion
        print(f"\n⚠️  WARNING: About to delete {len(users_to_delete)} users")
        print("Protected accounts (will NOT be deleted):")
        for email in PROTECTED_EMAILS:
            print(f"  ✅ {email}")
        print("\nUsers to be deleted:")
        for user in users_to_delete:
            print(f"  ❌ {user.email}")

        confirmation = input("\nProceed with deletion? (yes/no): ")
        if confirmation.lower() != "yes":
            logger.info("Deletion cancelled by user")
            return 0

        # Get user IDs to delete
        user_ids = [user.id for user in users_to_delete]

        # Delete related records manually (since chunks has ON DELETE RESTRICT)
        logger.info("Deleting related chunks...")
        chunks_stmt = delete(Chunk).where(Chunk.user_id.in_(user_ids))
        chunks_result = await session.execute(chunks_stmt)
        logger.info(f"  Deleted {chunks_result.rowcount} chunks")

        logger.info("Deleting related transcripts...")
        transcripts_stmt = delete(Transcript).where(Transcript.user_id.in_(user_ids))
        transcripts_result = await session.execute(transcripts_stmt)
        logger.info(f"  Deleted {transcripts_result.rowcount} transcripts")

        logger.info("Deleting related conversations...")
        conversations_stmt = delete(Conversation).where(Conversation.user_id.in_(user_ids))
        conversations_result = await session.execute(conversations_stmt)
        logger.info(f"  Deleted {conversations_result.rowcount} conversations")

        logger.info("Deleting related sessions...")
        sessions_stmt = delete(Session).where(Session.user_id.in_(user_ids))
        sessions_result = await session.execute(sessions_stmt)
        logger.info(f"  Deleted {sessions_result.rowcount} sessions")

        # Now delete users
        logger.info("Deleting users...")
        delete_stmt = delete(User).where(User.email.notin_(PROTECTED_EMAILS))
        result = await session.execute(delete_stmt)
        await session.commit()

        deleted_count = result.rowcount
        logger.success(f"✅ Successfully deleted {deleted_count} test users")

        # Verify remaining users
        remaining_stmt = select(User)
        remaining_result = await session.execute(remaining_stmt)
        remaining_users = list(remaining_result.scalars().all())

        logger.info(f"Remaining users in database: {len(remaining_users)}")
        for user in remaining_users:
            logger.info(f"  ✅ {user.email} (role: {user.role})")

        return deleted_count


async def main():
    """Main entry point"""
    logger.info("🗑️  Starting test user cleanup...")

    try:
        deleted_count = await cleanup_test_users()

        if deleted_count > 0:
            logger.success(f"✅ Cleanup complete! Deleted {deleted_count} test users")
        else:
            logger.info("No users were deleted")

        return 0
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
