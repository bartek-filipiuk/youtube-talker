"""
Reset Admin Password Script

Resets the password for admin@example.com to a known value.
Creates the admin user if it doesn't exist.

Usage:
    ADMIN_PASSWORD='your_password' python scripts/reset_admin_password.py

Environment Variables:
    ADMIN_PASSWORD: Password for the admin user (required)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.security import hash_password
from app.db.repositories.user_repo import UserRepository
from app.db.session import AsyncSessionLocal

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:
    print("❌ Error: ADMIN_PASSWORD environment variable not set")
    print("\nUsage:")
    print("  ADMIN_PASSWORD='your_password' python scripts/reset_admin_password.py")
    sys.exit(1)


async def reset_admin_password():
    """
    Reset admin password or create admin user if doesn't exist.
    """
    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)

        # Check if admin user exists
        admin_user = await repo.get_by_email(ADMIN_EMAIL)

        if admin_user:
            # User exists - update password
            new_password_hash = hash_password(ADMIN_PASSWORD)
            await repo.update_password(admin_user.id, new_password_hash)
            await db.commit()
            print(f"✅ Password reset for {ADMIN_EMAIL}")
            print(f"   New password: {ADMIN_PASSWORD}")
        else:
            # User doesn't exist - create admin user
            password_hash = hash_password(ADMIN_PASSWORD)
            admin_user = await repo.create(
                email=ADMIN_EMAIL,
                password_hash=password_hash,
            )
            # Set role to admin
            admin_user.role = "admin"
            await db.commit()
            print(f"✅ Created admin user: {ADMIN_EMAIL}")
            print(f"   Password: {ADMIN_PASSWORD}")
            print("   Role: admin")


if __name__ == "__main__":
    print("🔐 Resetting admin password...")
    print("=" * 60)
    asyncio.run(reset_admin_password())
    print("=" * 60)
    print("\n✅ Done! You can now log in with:")
    print(f"   Email: {ADMIN_EMAIL}")
    print(f"   Password: {ADMIN_PASSWORD}")
    print("\n⚠️  Remember to change this password after logging in!")
