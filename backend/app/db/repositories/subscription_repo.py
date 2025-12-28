"""
Subscription Repository

Database operations for SubscriptionPlan and UserSubscription models.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import SubscriptionPlan, UserSubscription


class SubscriptionRepository:
    """Repository for subscription-related database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ============ SubscriptionPlan Operations ============

    async def get_plan_by_name(self, name: str) -> Optional[SubscriptionPlan]:
        """
        Get subscription plan by name (free, pro, enterprise).

        Args:
            name: Plan name

        Returns:
            SubscriptionPlan or None
        """
        result = await self.session.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.name == name,
                SubscriptionPlan.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_plan_by_id(self, plan_id: UUID) -> Optional[SubscriptionPlan]:
        """Get subscription plan by ID."""
        result = await self.session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def get_plan_by_stripe_price(self, price_id: str) -> Optional[SubscriptionPlan]:
        """
        Get subscription plan by Stripe Price ID.

        Args:
            price_id: Stripe Price ID (price_xxx)

        Returns:
            SubscriptionPlan or None
        """
        result = await self.session.execute(
            select(SubscriptionPlan).where(
                (SubscriptionPlan.stripe_price_id_monthly == price_id)
                | (SubscriptionPlan.stripe_price_id_annual == price_id),
                SubscriptionPlan.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_active_plans(self) -> list[SubscriptionPlan]:
        """Get all active subscription plans."""
        result = await self.session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
        )
        return list(result.scalars().all())

    async def get_plan_by_id(self, plan_id: UUID) -> Optional[SubscriptionPlan]:
        """Get a subscription plan by ID."""
        result = await self.session.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.id == plan_id,
                SubscriptionPlan.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    # ============ UserSubscription Operations ============

    async def get_user_subscription(self, user_id: UUID) -> Optional[UserSubscription]:
        """
        Get user's subscription with plan details.

        Args:
            user_id: User's UUID

        Returns:
            UserSubscription with plan loaded, or None
        """
        result = await self.session.execute(
            select(UserSubscription)
            .options(joinedload(UserSubscription.plan))
            .where(UserSubscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_subscription_by_stripe_id(
        self, stripe_subscription_id: str
    ) -> Optional[UserSubscription]:
        """Get subscription by Stripe Subscription ID."""
        result = await self.session.execute(
            select(UserSubscription)
            .options(joinedload(UserSubscription.plan))
            .where(UserSubscription.stripe_subscription_id == stripe_subscription_id)
        )
        return result.scalar_one_or_none()

    async def get_subscription_by_stripe_customer(
        self, stripe_customer_id: str
    ) -> Optional[UserSubscription]:
        """Get subscription by Stripe Customer ID."""
        result = await self.session.execute(
            select(UserSubscription)
            .options(joinedload(UserSubscription.plan))
            .where(UserSubscription.stripe_customer_id == stripe_customer_id)
        )
        return result.scalar_one_or_none()

    async def create_subscription(
        self,
        user_id: UUID,
        plan_id: UUID,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        status: str = "active",
        current_period_start: Optional[datetime] = None,
        current_period_end: Optional[datetime] = None,
        trial_end: Optional[datetime] = None,
    ) -> UserSubscription:
        """
        Create a new user subscription.

        Args:
            user_id: User's UUID
            plan_id: SubscriptionPlan UUID
            stripe_customer_id: Stripe Customer ID (optional for free plan)
            stripe_subscription_id: Stripe Subscription ID (optional for free plan)
            status: Subscription status (active, trialing, etc.)
            current_period_start: Start of billing period
            current_period_end: End of billing period
            trial_end: End of trial period

        Returns:
            Created UserSubscription
        """
        subscription = UserSubscription(
            user_id=user_id,
            plan_id=plan_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            trial_end=trial_end,
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def update_subscription(
        self,
        user_id: UUID,
        **kwargs,
    ) -> Optional[UserSubscription]:
        """
        Update user subscription fields.

        Args:
            user_id: User's UUID
            **kwargs: Fields to update (plan_id, status, stripe_ids, periods, etc.)

        Returns:
            Updated UserSubscription or None if not found
        """
        # Add updated_at timestamp
        kwargs["updated_at"] = datetime.now(timezone.utc)

        await self.session.execute(
            update(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .values(**kwargs)
        )
        await self.session.flush()

        return await self.get_user_subscription(user_id)

    async def update_subscription_by_stripe_id(
        self,
        stripe_subscription_id: str,
        **kwargs,
    ) -> Optional[UserSubscription]:
        """
        Update subscription by Stripe Subscription ID.

        Used by webhooks to update subscription status.

        Args:
            stripe_subscription_id: Stripe Subscription ID
            **kwargs: Fields to update

        Returns:
            Updated UserSubscription or None if not found
        """
        kwargs["updated_at"] = datetime.now(timezone.utc)

        await self.session.execute(
            update(UserSubscription)
            .where(UserSubscription.stripe_subscription_id == stripe_subscription_id)
            .values(**kwargs)
        )
        await self.session.flush()

        return await self.get_subscription_by_stripe_id(stripe_subscription_id)

    async def cancel_subscription(
        self,
        user_id: UUID,
        at_period_end: bool = True,
    ) -> Optional[UserSubscription]:
        """
        Mark subscription as canceled.

        Args:
            user_id: User's UUID
            at_period_end: If True, set cancel_at_period_end flag
                          If False, immediately set status to canceled

        Returns:
            Updated UserSubscription
        """
        if at_period_end:
            return await self.update_subscription(
                user_id,
                cancel_at_period_end=True,
            )
        else:
            return await self.update_subscription(
                user_id,
                status="canceled",
                cancel_at_period_end=False,
            )
