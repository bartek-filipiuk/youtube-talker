"""
Stripe Webhook Handler

Handles incoming Stripe webhook events for subscription lifecycle.
This endpoint must NOT require authentication - Stripe sends events directly.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.services.billing_service import BillingService
from app.services.stripe_service import StripeService


# Create router - no auth prefix
router = APIRouter(prefix="/api/stripe", tags=["stripe-webhook"])


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.

    This endpoint receives events from Stripe for:
    - checkout.session.completed: User completed checkout
    - customer.subscription.created: New subscription
    - customer.subscription.updated: Subscription changed
    - customer.subscription.deleted: Subscription canceled
    - invoice.paid: Payment succeeded
    - invoice.payment_failed: Payment failed

    No authentication required - uses Stripe signature verification.

    Args:
        request: Raw request with webhook payload

    Returns:
        Success acknowledgment

    Raises:
        HTTPException(400): Invalid signature or payload
    """
    # Get raw payload for signature verification
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    if not signature:
        logger.warning("Stripe webhook received without signature")
        raise HTTPException(status_code=400, detail="Missing signature")

    # Verify signature and parse event
    try:
        event = StripeService.verify_webhook_signature(payload, signature)
    except ValueError as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    event_data = event["data"]["object"]

    logger.info(f"Received Stripe webhook: {event_type}")

    # Process event with database session
    async with AsyncSessionLocal() as db:
        billing_service = BillingService(db)

        try:
            if event_type == "checkout.session.completed":
                await handle_checkout_completed(billing_service, event_data)

            elif event_type == "customer.subscription.created":
                await handle_subscription_created(billing_service, event_data)

            elif event_type == "customer.subscription.updated":
                await handle_subscription_updated(billing_service, event_data)

            elif event_type == "customer.subscription.deleted":
                await handle_subscription_deleted(billing_service, event_data)

            elif event_type == "invoice.paid":
                await handle_invoice_paid(billing_service, event_data)

            elif event_type == "invoice.payment_failed":
                await handle_invoice_payment_failed(billing_service, event_data)

            else:
                logger.debug(f"Unhandled webhook event type: {event_type}")

            await db.commit()

        except Exception as e:
            logger.exception(f"Error processing webhook {event_type}: {e}")
            await db.rollback()
            # Return 200 to prevent Stripe retries for processing errors
            # Log error for manual investigation

    return {"status": "received"}


async def handle_checkout_completed(
    billing_service: BillingService,
    session_data: dict,
):
    """
    Handle checkout.session.completed event.

    Called when user completes Stripe Checkout.

    Args:
        billing_service: BillingService instance
        session_data: Stripe Session object
    """
    # Get user_id from metadata
    metadata = session_data.get("metadata", {})
    user_id_str = metadata.get("user_id")

    if not user_id_str:
        logger.error("Checkout completed without user_id in metadata")
        return

    user_id = UUID(user_id_str)
    customer_id = session_data.get("customer")
    subscription_id = session_data.get("subscription")

    if not subscription_id:
        logger.error(f"Checkout completed without subscription ID for user {user_id}")
        return

    await billing_service.handle_checkout_completed(
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        user_id=user_id,
    )

    logger.info(f"Checkout completed for user {user_id}, subscription {subscription_id}")


async def handle_subscription_created(
    billing_service: BillingService,
    subscription_data: dict,
):
    """
    Handle customer.subscription.created event.

    Note: Most logic is in checkout.session.completed.
    This is a backup for subscriptions created outside checkout.

    Args:
        billing_service: BillingService instance
        subscription_data: Stripe Subscription object
    """
    subscription_id = subscription_data.get("id")
    logger.info(f"Subscription created: {subscription_id}")
    # No action needed - checkout.session.completed handles initial setup


async def handle_subscription_updated(
    billing_service: BillingService,
    subscription_data: dict,
):
    """
    Handle customer.subscription.updated event.

    Called when subscription status changes, period updates, or cancellation pending.

    Args:
        billing_service: BillingService instance
        subscription_data: Stripe Subscription object
    """
    subscription_id = subscription_data.get("id")
    status = subscription_data.get("status")
    cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)

    current_period_start = datetime.fromtimestamp(
        subscription_data.get("current_period_start", 0), tz=timezone.utc
    )
    current_period_end = datetime.fromtimestamp(
        subscription_data.get("current_period_end", 0), tz=timezone.utc
    )

    trial_end = None
    if subscription_data.get("trial_end"):
        trial_end = datetime.fromtimestamp(
            subscription_data.get("trial_end"), tz=timezone.utc
        )

    await billing_service.handle_subscription_updated(
        stripe_subscription_id=subscription_id,
        status=status,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
        cancel_at_period_end=cancel_at_period_end,
        trial_end=trial_end,
    )

    logger.info(f"Subscription {subscription_id} updated: status={status}")


async def handle_subscription_deleted(
    billing_service: BillingService,
    subscription_data: dict,
):
    """
    Handle customer.subscription.deleted event.

    Called when subscription is fully canceled (not just pending cancellation).
    Downgrades user to free plan.

    Args:
        billing_service: BillingService instance
        subscription_data: Stripe Subscription object
    """
    subscription_id = subscription_data.get("id")

    await billing_service.handle_subscription_deleted(
        stripe_subscription_id=subscription_id,
    )

    logger.info(f"Subscription {subscription_id} deleted, user downgraded to free")


async def handle_invoice_paid(
    billing_service: BillingService,
    invoice_data: dict,
):
    """
    Handle invoice.paid event.

    Called on successful payment (initial and renewals).
    Resets usage counters for new billing period.

    Args:
        billing_service: BillingService instance
        invoice_data: Stripe Invoice object
    """
    subscription_id = invoice_data.get("subscription")

    if not subscription_id:
        # Not a subscription invoice (one-time payment)
        return

    await billing_service.handle_invoice_paid(
        stripe_subscription_id=subscription_id,
    )

    logger.info(f"Invoice paid for subscription {subscription_id}")


async def handle_invoice_payment_failed(
    billing_service: BillingService,
    invoice_data: dict,
):
    """
    Handle invoice.payment_failed event.

    Called when payment fails. Stripe will retry automatically.
    User's subscription status will be updated to 'past_due' by
    customer.subscription.updated event.

    Args:
        billing_service: BillingService instance
        invoice_data: Stripe Invoice object
    """
    subscription_id = invoice_data.get("subscription")
    customer_email = invoice_data.get("customer_email")
    attempt_count = invoice_data.get("attempt_count", 0)

    logger.warning(
        f"Invoice payment failed for subscription {subscription_id}, "
        f"email={customer_email}, attempt={attempt_count}"
    )

    # TODO: Send dunning email to user
    # For now, rely on Stripe's automatic emails
