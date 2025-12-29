"""
Stripe Service

Business logic for Stripe integration including checkout sessions,
customer portal, and subscription management.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import stripe
from loguru import logger

from app.config import settings


# Initialize Stripe with secret key
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """
    Service for Stripe payment integration.

    Handles:
    - Checkout session creation for subscription signup
    - Customer portal session creation for self-service management
    - Subscription retrieval and cancellation
    - Webhook event verification
    """

    def __init__(self):
        """Initialize Stripe service."""
        if not settings.STRIPE_SECRET_KEY:
            logger.warning("STRIPE_SECRET_KEY not configured - Stripe features disabled")

    async def create_checkout_session(
        self,
        user_id: UUID,
        user_email: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        trial_days: int = 7,
    ) -> dict:
        """
        Create a Stripe Checkout session for subscription signup.

        Args:
            user_id: Internal user UUID (stored in metadata for webhook)
            user_email: User's email for Stripe customer
            price_id: Stripe Price ID (price_xxx)
            success_url: URL to redirect after successful checkout
            cancel_url: URL to redirect if user cancels
            trial_days: Number of trial days (default 7)

        Returns:
            dict with checkout_url and session_id

        Raises:
            stripe.error.StripeError: If Stripe API fails
        """
        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                customer_email=user_email,
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                subscription_data={
                    "trial_period_days": trial_days,
                    "metadata": {
                        "user_id": str(user_id),
                    },
                },
                metadata={
                    "user_id": str(user_id),
                },
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=True,
            )

            logger.info(f"Created Stripe checkout session for user {user_id}")

            return {
                "checkout_url": session.url,
                "session_id": session.id,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout session creation failed: {e}")
            raise

    async def create_portal_session(
        self,
        stripe_customer_id: str,
        return_url: str,
    ) -> dict:
        """
        Create a Stripe Customer Portal session for subscription management.

        Users can:
        - Update payment method
        - Cancel subscription
        - View billing history
        - Download invoices

        Args:
            stripe_customer_id: Stripe Customer ID (cus_xxx)
            return_url: URL to redirect after portal session

        Returns:
            dict with portal_url

        Raises:
            stripe.error.StripeError: If Stripe API fails
        """
        try:
            session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=return_url,
            )

            logger.info(f"Created Stripe portal session for customer {stripe_customer_id}")

            return {
                "portal_url": session.url,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe portal session creation failed: {e}")
            raise

    async def get_subscription(self, subscription_id: str) -> Optional[dict]:
        """
        Get subscription details from Stripe.

        Args:
            subscription_id: Stripe Subscription ID (sub_xxx)

        Returns:
            Subscription details dict or None if not found
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)

            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": datetime.fromtimestamp(
                    subscription.current_period_start, tz=timezone.utc
                ),
                "current_period_end": datetime.fromtimestamp(
                    subscription.current_period_end, tz=timezone.utc
                ),
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "trial_end": (
                    datetime.fromtimestamp(subscription.trial_end, tz=timezone.utc)
                    if subscription.trial_end
                    else None
                ),
                "customer_id": subscription.customer,
            }

        except stripe.error.InvalidRequestError:
            logger.warning(f"Subscription not found: {subscription_id}")
            return None
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve subscription: {e}")
            raise

    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True,
    ) -> dict:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe Subscription ID (sub_xxx)
            at_period_end: If True, cancel at end of billing period (default)
                          If False, cancel immediately

        Returns:
            Updated subscription details
        """
        try:
            if at_period_end:
                # Cancel at period end (user keeps access until then)
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                )
                logger.info(f"Subscription {subscription_id} set to cancel at period end")
            else:
                # Cancel immediately
                subscription = stripe.Subscription.cancel(subscription_id)
                logger.info(f"Subscription {subscription_id} canceled immediately")

            return {
                "id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise

    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> dict:
        """
        Verify Stripe webhook signature and parse event.

        Args:
            payload: Raw request body bytes
            signature: Stripe-Signature header value

        Returns:
            Parsed Stripe event object

        Raises:
            ValueError: If signature verification fails
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                settings.STRIPE_WEBHOOK_SECRET,
            )
            return event

        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {e}")
            raise ValueError("Invalid webhook signature")

    async def get_customer(self, customer_id: str) -> Optional[dict]:
        """
        Get customer details from Stripe.

        Args:
            customer_id: Stripe Customer ID (cus_xxx)

        Returns:
            Customer details dict or None if not found
        """
        try:
            customer = stripe.Customer.retrieve(customer_id)

            return {
                "id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "created": datetime.fromtimestamp(customer.created, tz=timezone.utc),
            }

        except stripe.error.InvalidRequestError:
            logger.warning(f"Customer not found: {customer_id}")
            return None
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve customer: {e}")
            raise
