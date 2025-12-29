"""
Billing Service

Business logic for subscription management, usage tracking, and billing operations.
Orchestrates StripeService, SubscriptionRepository, and UsageRepository.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, SubscriptionPlan, UserSubscription, UsageTracking
from app.db.repositories.subscription_repo import SubscriptionRepository
from app.db.repositories.usage_repo import UsageRepository
from app.services.stripe_service import StripeService


class BillingService:
    """
    Billing service for subscription and usage management.

    Handles:
    - Subscription creation and management
    - Usage tracking and limit enforcement
    - Stripe integration coordination
    - Plan upgrades/downgrades
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize billing service with database session.

        Args:
            db: SQLAlchemy async session
        """
        self.db = db
        self.subscription_repo = SubscriptionRepository(db)
        self.usage_repo = UsageRepository(db)
        self.stripe_service = StripeService()

    # ============ Subscription Management ============

    async def get_user_subscription(self, user_id: UUID) -> Optional[UserSubscription]:
        """
        Get user's subscription with plan details.

        If user has no subscription, creates a Free subscription.

        Args:
            user_id: User's UUID

        Returns:
            UserSubscription with plan loaded
        """
        subscription = await self.subscription_repo.get_user_subscription(user_id)

        if not subscription:
            # Create free subscription for new user
            subscription = await self.create_free_subscription(user_id)

        return subscription

    async def create_free_subscription(self, user_id: UUID) -> UserSubscription:
        """
        Create a free tier subscription for a new user.

        Args:
            user_id: User's UUID

        Returns:
            Created UserSubscription
        """
        free_plan = await self.subscription_repo.get_plan_by_name("free")
        if not free_plan:
            raise ValueError("Free plan not found in database. Run seed_plans.py")

        # Free plan has monthly billing period (for usage tracking)
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (period_start + timedelta(days=32)).replace(day=1)
        period_end = next_month

        subscription = await self.subscription_repo.create_subscription(
            user_id=user_id,
            plan_id=free_plan.id,
            status="active",
            current_period_start=period_start,
            current_period_end=period_end,
        )

        # Create usage tracking for this period
        await self.usage_repo.get_or_create_current_usage(
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
        )

        logger.info(f"Created free subscription for user {user_id}")
        return subscription

    async def create_checkout_session(
        self,
        user: User,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        """
        Create a Stripe Checkout session for subscription upgrade.

        Args:
            user: User object
            price_id: Stripe Price ID
            success_url: Redirect URL after success
            cancel_url: Redirect URL if canceled

        Returns:
            dict with checkout_url and session_id
        """
        return await self.stripe_service.create_checkout_session(
            user_id=user.id,
            user_email=user.email,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            trial_days=7,
        )

    async def create_portal_session(
        self,
        user_id: UUID,
        return_url: str,
    ) -> dict:
        """
        Create a Stripe Customer Portal session.

        Args:
            user_id: User's UUID
            return_url: Redirect URL after portal

        Returns:
            dict with portal_url

        Raises:
            ValueError: If user has no Stripe customer ID
        """
        subscription = await self.get_user_subscription(user_id)

        if not subscription or not subscription.stripe_customer_id:
            raise ValueError("User has no active Stripe subscription")

        return await self.stripe_service.create_portal_session(
            stripe_customer_id=subscription.stripe_customer_id,
            return_url=return_url,
        )

    # ============ Usage Tracking ============

    async def _maybe_advance_free_tier_period(
        self, subscription: UserSubscription
    ) -> UserSubscription:
        """
        Check if free-tier billing period has expired and advance it if needed.

        Free-tier subscriptions don't have Stripe webhooks to reset their period,
        so we need to check and advance manually.

        Args:
            subscription: User's subscription

        Returns:
            Updated subscription (possibly with new period)
        """
        # Only advance for free tier (no Stripe subscription)
        if subscription.stripe_subscription_id:
            return subscription

        now = datetime.now(timezone.utc)

        # Check if period has expired
        if subscription.current_period_end and now >= subscription.current_period_end:
            # Calculate new period (next calendar month)
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = (period_start + timedelta(days=32)).replace(day=1)
            period_end = next_month

            # Update subscription period
            updated = await self.subscription_repo.update_subscription(
                user_id=subscription.user_id,
                current_period_start=period_start,
                current_period_end=period_end,
            )

            if updated:
                logger.info(
                    f"Advanced free-tier period for user {subscription.user_id}: "
                    f"{period_start} - {period_end}"
                )
                return updated

        return subscription

    async def get_current_usage(self, user_id: UUID) -> Optional[UsageTracking]:
        """
        Get user's current period usage.

        Creates usage record if not exists. For free-tier users,
        automatically advances the billing period if it has expired.

        Args:
            user_id: User's UUID

        Returns:
            UsageTracking for current period
        """
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            return None

        # Check and advance period for free-tier users if expired
        subscription = await self._maybe_advance_free_tier_period(subscription)

        # Ensure usage record exists for current period
        return await self.usage_repo.get_or_create_current_usage(
            user_id=user_id,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
        )

    async def check_video_limit(self, user_id: UUID) -> tuple[bool, int, Optional[int]]:
        """
        Check if user can load another video.

        Args:
            user_id: User's UUID

        Returns:
            Tuple of (can_load, videos_used, video_limit)
            video_limit is None if unlimited
        """
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            return False, 0, 0

        usage = await self.get_current_usage(user_id)
        if not usage:
            return False, 0, 0

        video_limit = subscription.plan.video_limit
        videos_used = usage.videos_used

        # None limit = unlimited
        if video_limit is None:
            return True, videos_used, None

        can_load = videos_used < video_limit
        return can_load, videos_used, video_limit

    async def check_message_limit(self, user_id: UUID) -> tuple[bool, int, Optional[int]]:
        """
        Check if user can send another message.

        Args:
            user_id: User's UUID

        Returns:
            Tuple of (can_send, messages_used, message_limit)
            message_limit is None if unlimited
        """
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            return False, 0, 0

        usage = await self.get_current_usage(user_id)
        if not usage:
            return False, 0, 0

        message_limit = subscription.plan.message_limit
        messages_used = usage.messages_used

        # None limit = unlimited
        if message_limit is None:
            return True, messages_used, None

        can_send = messages_used < message_limit
        return can_send, messages_used, message_limit

    async def increment_video_usage(self, user_id: UUID) -> Optional[UsageTracking]:
        """
        Increment video usage count after successful video load.

        Args:
            user_id: User's UUID

        Returns:
            Updated UsageTracking
        """
        return await self.usage_repo.increment_videos(user_id)

    async def increment_message_usage(self, user_id: UUID) -> Optional[UsageTracking]:
        """
        Increment message usage count after successful message.

        Args:
            user_id: User's UUID

        Returns:
            Updated UsageTracking
        """
        return await self.usage_repo.increment_messages(user_id)

    # ============ Webhook Handlers ============

    async def handle_checkout_completed(
        self,
        stripe_customer_id: str,
        stripe_subscription_id: str,
        user_id: UUID,
    ) -> UserSubscription:
        """
        Handle successful Stripe Checkout completion.

        Updates user's subscription with Stripe IDs and Pro plan.

        Args:
            stripe_customer_id: Stripe Customer ID
            stripe_subscription_id: Stripe Subscription ID
            user_id: User's UUID from metadata

        Returns:
            Updated UserSubscription
        """
        # Get subscription details from Stripe
        stripe_sub = await self.stripe_service.get_subscription(stripe_subscription_id)
        if not stripe_sub:
            raise ValueError(f"Subscription not found: {stripe_subscription_id}")

        # Get Pro plan
        pro_plan = await self.subscription_repo.get_plan_by_name("pro")
        if not pro_plan:
            raise ValueError("Pro plan not found")

        # Update user subscription
        subscription = await self.subscription_repo.update_subscription(
            user_id=user_id,
            plan_id=pro_plan.id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            status=stripe_sub["status"],
            current_period_start=stripe_sub["current_period_start"],
            current_period_end=stripe_sub["current_period_end"],
            trial_end=stripe_sub["trial_end"],
            cancel_at_period_end=False,
        )

        # Create/update usage tracking for new period
        await self.usage_repo.get_or_create_current_usage(
            user_id=user_id,
            period_start=stripe_sub["current_period_start"],
            period_end=stripe_sub["current_period_end"],
        )

        logger.info(f"User {user_id} upgraded to Pro plan")
        return subscription

    async def handle_subscription_updated(
        self,
        stripe_subscription_id: str,
        status: str,
        current_period_start: datetime,
        current_period_end: datetime,
        cancel_at_period_end: bool,
        trial_end: Optional[datetime],
    ) -> Optional[UserSubscription]:
        """
        Handle Stripe subscription update event.

        Args:
            stripe_subscription_id: Stripe Subscription ID
            status: New subscription status
            current_period_start: Start of billing period
            current_period_end: End of billing period
            cancel_at_period_end: Whether subscription will cancel
            trial_end: End of trial period

        Returns:
            Updated UserSubscription or None if not found
        """
        subscription = await self.subscription_repo.update_subscription_by_stripe_id(
            stripe_subscription_id=stripe_subscription_id,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            cancel_at_period_end=cancel_at_period_end,
            trial_end=trial_end,
        )

        if subscription:
            # Reset usage for new period if period changed
            await self.usage_repo.get_or_create_current_usage(
                user_id=subscription.user_id,
                period_start=current_period_start,
                period_end=current_period_end,
            )

            logger.info(
                f"Updated subscription {stripe_subscription_id}: status={status}, "
                f"cancel_at_period_end={cancel_at_period_end}"
            )

        return subscription

    async def handle_subscription_deleted(
        self,
        stripe_subscription_id: str,
    ) -> Optional[UserSubscription]:
        """
        Handle Stripe subscription deletion/cancellation.

        Downgrades user to free plan.

        Args:
            stripe_subscription_id: Stripe Subscription ID

        Returns:
            Updated UserSubscription or None if not found
        """
        subscription = await self.subscription_repo.get_subscription_by_stripe_id(
            stripe_subscription_id
        )
        if not subscription:
            logger.warning(f"Subscription not found for deletion: {stripe_subscription_id}")
            return None

        # Get free plan for downgrade
        free_plan = await self.subscription_repo.get_plan_by_name("free")
        if not free_plan:
            raise ValueError("Free plan not found")

        # Reset billing period to monthly
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (period_start + timedelta(days=32)).replace(day=1)

        # Downgrade to free
        updated = await self.subscription_repo.update_subscription(
            user_id=subscription.user_id,
            plan_id=free_plan.id,
            status="active",
            current_period_start=period_start,
            current_period_end=next_month,
            cancel_at_period_end=False,
            trial_end=None,
        )

        # Create usage tracking for new period
        await self.usage_repo.get_or_create_current_usage(
            user_id=subscription.user_id,
            period_start=period_start,
            period_end=next_month,
        )

        logger.info(f"Downgraded user {subscription.user_id} to free plan")
        return updated

    async def handle_invoice_paid(
        self,
        stripe_subscription_id: str,
    ) -> Optional[UserSubscription]:
        """
        Handle successful invoice payment (subscription renewal).

        Resets usage for new billing period.

        Args:
            stripe_subscription_id: Stripe Subscription ID

        Returns:
            UserSubscription or None if not found
        """
        # Get fresh subscription data from Stripe
        stripe_sub = await self.stripe_service.get_subscription(stripe_subscription_id)
        if not stripe_sub:
            return None

        # Update subscription with new period
        subscription = await self.subscription_repo.update_subscription_by_stripe_id(
            stripe_subscription_id=stripe_subscription_id,
            status=stripe_sub["status"],
            current_period_start=stripe_sub["current_period_start"],
            current_period_end=stripe_sub["current_period_end"],
        )

        if subscription:
            # Create new usage tracking record for new period
            await self.usage_repo.reset_usage(
                user_id=subscription.user_id,
                new_period_start=stripe_sub["current_period_start"],
                new_period_end=stripe_sub["current_period_end"],
            )

            logger.info(
                f"Subscription {stripe_subscription_id} renewed. "
                f"New period: {stripe_sub['current_period_start']} - {stripe_sub['current_period_end']}"
            )

        return subscription

    # ============ Helper Methods ============

    async def get_all_plans(self) -> list[SubscriptionPlan]:
        """Get all active subscription plans."""
        return await self.subscription_repo.get_all_active_plans()

    async def get_plan_by_id(self, plan_id: UUID) -> Optional[SubscriptionPlan]:
        """Get a subscription plan by ID."""
        return await self.subscription_repo.get_plan_by_id(plan_id)

    def is_pro_subscription(self, subscription: Optional[UserSubscription]) -> bool:
        """Check if subscription is Pro tier."""
        if not subscription:
            return False
        return subscription.plan.name == "pro" and subscription.status in (
            "active",
            "trialing",
        )

    def is_trialing(self, subscription: Optional[UserSubscription]) -> bool:
        """Check if subscription is in trial period."""
        if not subscription:
            return False
        return subscription.status == "trialing"
