"""
Seed Subscription Plans Script

Populates the subscription_plans table with default subscription tiers.
Run this script after database migrations to initialize subscription plans.

Usage:
    python scripts/seed_plans.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.db.models import SubscriptionPlan


async def seed_plans():
    """
    Seed the subscription_plans table with default subscription tiers.

    Subscription Tiers:
    - Free: 3 videos/month, 50 messages/month, $0
    - Pro: 50 videos/month, 1000 messages/month, $12/month or $115/year
    - Enterprise: Custom limits, contact sales

    Run this script:
    - After initial database setup
    - When subscription plans change
    """

    # Create async session
    async with AsyncSessionLocal() as db:
        # Define subscription plan configurations
        plan_configs = [
            {
                "name": "free",
                "display_name": "Free",
                "stripe_price_id_monthly": None,
                "stripe_price_id_annual": None,
                "monthly_price_cents": 0,
                "annual_price_cents": None,
                "video_limit": 3,
                "message_limit": 50,
                "features": {
                    "priority_support": False,
                    "api_access": False,
                    "custom_branding": False,
                },
            },
            {
                "name": "pro",
                "display_name": "Pro",
                "stripe_price_id_monthly": None,  # Set after Stripe setup
                "stripe_price_id_annual": None,   # Set after Stripe setup
                "monthly_price_cents": 1200,      # $12.00
                "annual_price_cents": 11500,      # $115.00 (2 months free)
                "video_limit": 50,
                "message_limit": 1000,
                "features": {
                    "priority_support": True,
                    "api_access": False,
                    "custom_branding": False,
                },
            },
            {
                "name": "enterprise",
                "display_name": "Enterprise",
                "stripe_price_id_monthly": None,  # Manual invoicing
                "stripe_price_id_annual": None,
                "monthly_price_cents": 0,         # Custom pricing
                "annual_price_cents": None,
                "video_limit": None,              # Unlimited
                "message_limit": None,            # Unlimited
                "features": {
                    "priority_support": True,
                    "api_access": True,
                    "custom_branding": True,
                    "dedicated_account_manager": True,
                    "sla": True,
                },
            },
        ]

        print("🌱 Seeding subscription_plans table...")
        print(f"   Found {len(plan_configs)} plans to insert")
        print()

        created_count = 0
        updated_count = 0

        for config in plan_configs:
            plan_name = config["name"]

            # Check if plan already exists
            result = await db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.name == plan_name)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Plan exists - check if it needs updating
                needs_update = (
                    existing.display_name != config["display_name"]
                    or existing.monthly_price_cents != config["monthly_price_cents"]
                    or existing.annual_price_cents != config["annual_price_cents"]
                    or existing.video_limit != config["video_limit"]
                    or existing.message_limit != config["message_limit"]
                    or existing.features != config["features"]
                )

                if needs_update:
                    print(f"   ⚠️  Updating plan: {plan_name}")
                    existing.display_name = config["display_name"]
                    existing.monthly_price_cents = config["monthly_price_cents"]
                    existing.annual_price_cents = config["annual_price_cents"]
                    existing.video_limit = config["video_limit"]
                    existing.message_limit = config["message_limit"]
                    existing.features = config["features"]
                    updated_count += 1
                else:
                    print(f"   ✓ {plan_name} - already configured")
            else:
                # Create new plan
                plan = SubscriptionPlan(**config)
                db.add(plan)
                print(f"   ✅ Created plan: {plan_name}")
                created_count += 1

        await db.commit()

        print()
        print(f"✨ Seeding complete!")
        print(f"   Created: {created_count} new plans")
        print(f"   Updated: {updated_count} plans")
        print()

        # Verify all active plans
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
        )
        all_plans = result.scalars().all()

        print(f"📊 Active subscription plans: {len(all_plans)}")
        print()
        print("Plan         | Price/mo | Price/yr  | Videos | Messages | Features")
        print("-" * 80)

        for p in all_plans:
            name = p.display_name.ljust(12)
            monthly = f"${p.monthly_price_cents / 100:.2f}" if p.monthly_price_cents else "Custom"
            annual = f"${p.annual_price_cents / 100:.2f}" if p.annual_price_cents else "N/A"
            videos = str(p.video_limit) if p.video_limit else "Unlimited"
            messages = str(p.message_limit) if p.message_limit else "Unlimited"
            features = ", ".join([k for k, v in p.features.items() if v])

            print(
                f"{name} | {monthly:8} | {annual:9} | {videos:6} | {messages:8} | {features}"
            )

        print()


if __name__ == "__main__":
    print("=" * 60)
    print("Qivio - Seed Subscription Plans")
    print("=" * 60)
    print()

    try:
        asyncio.run(seed_plans())
        print("✅ Plan seeding successful!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error seeding plans: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
