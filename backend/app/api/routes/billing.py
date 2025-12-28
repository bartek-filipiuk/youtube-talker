"""
Billing API Endpoints

REST endpoints for subscription management, checkout, and usage tracking.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_current_user
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    PortalRequest,
    PortalResponse,
    SubscriptionResponse,
    UsageResponse,
    BillingStatusResponse,
    PlansListResponse,
    PlanResponse,
)
from app.services.billing_service import BillingService

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans", response_model=PlansListResponse)
async def list_plans(
    db: AsyncSession = Depends(get_db),
) -> PlansListResponse:
    """
    List all available subscription plans.

    Public endpoint - no authentication required.

    Returns:
        List of subscription plans with pricing and limits
    """
    billing_service = BillingService(db)
    plans = await billing_service.get_all_plans()

    return PlansListResponse(
        plans=[PlanResponse.model_validate(plan) for plan in plans]
    )


@router.get("/status", response_model=BillingStatusResponse)
async def get_billing_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingStatusResponse:
    """
    Get current user's billing status.

    Returns subscription details, usage stats, and status flags.

    Args:
        user: Authenticated user

    Returns:
        Combined billing status
    """
    billing_service = BillingService(db)

    # Get subscription (creates free subscription if none exists)
    subscription = await billing_service.get_user_subscription(user.id)

    # Get usage
    usage = await billing_service.get_current_usage(user.id)

    # Build response
    subscription_response = None
    usage_response = None

    if subscription:
        subscription_response = SubscriptionResponse(
            id=subscription.id,
            plan=PlanResponse.model_validate(subscription.plan),
            status=subscription.status,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            cancel_at_period_end=subscription.cancel_at_period_end,
            trial_end=subscription.trial_end,
        )

    if usage and subscription:
        usage_response = UsageResponse(
            videos_used=usage.videos_used,
            videos_limit=subscription.plan.video_limit,
            messages_used=usage.messages_used,
            messages_limit=subscription.plan.message_limit,
            period_start=usage.period_start,
            period_end=usage.period_end,
        )

    return BillingStatusResponse(
        subscription=subscription_response,
        usage=usage_response,
        is_pro=billing_service.is_pro_subscription(subscription),
        is_trialing=billing_service.is_trialing(subscription),
        is_canceled=subscription.cancel_at_period_end if subscription else False,
    )


@router.post("/checkout", response_model=CheckoutResponse)
@limiter.limit("10/minute")
async def create_checkout(
    request: Request,
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    """
    Create a Stripe Checkout session for subscription upgrade.

    Rate limit: 10 requests per minute.

    Args:
        body: Checkout request with plan_id and billing_cycle
        user: Authenticated user

    Returns:
        Checkout URL to redirect user

    Raises:
        HTTPException(400): If checkout creation fails
        HTTPException(404): If plan not found
    """
    billing_service = BillingService(db)

    # Look up the plan
    plan = await billing_service.get_plan_by_id(body.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Get the appropriate Stripe price ID
    if body.billing_cycle == "annual":
        price_id = plan.stripe_price_id_annual
    else:
        price_id = plan.stripe_price_id_monthly

    if not price_id:
        raise HTTPException(
            status_code=400,
            detail=f"No Stripe price configured for {body.billing_cycle} billing"
        )

    # Generate URLs based on frontend origin
    origin = request.headers.get("origin", "http://localhost:4321")
    success_url = f"{origin}/billing?success=true"
    cancel_url = f"{origin}/pricing?canceled=true"

    try:
        result = await billing_service.create_checkout_session(
            user=user,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return CheckoutResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/portal", response_model=PortalResponse)
@limiter.limit("10/minute")
async def create_portal(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortalResponse:
    """
    Create a Stripe Customer Portal session.

    Allows users to manage their subscription:
    - Update payment method
    - Cancel subscription
    - View invoices

    Rate limit: 10 requests per minute.

    Args:
        user: Authenticated user

    Returns:
        Portal URL to redirect user

    Raises:
        HTTPException(400): If user has no Stripe subscription
    """
    billing_service = BillingService(db)

    # Generate return URL from origin
    origin = request.headers.get("origin", "http://localhost:4321")
    return_url = f"{origin}/billing"

    try:
        result = await billing_service.create_portal_session(
            user_id=user.id,
            return_url=return_url,
        )
        return PortalResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create portal session")


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageResponse:
    """
    Get current user's usage for this billing period.

    Args:
        user: Authenticated user

    Returns:
        Usage stats with limits

    Raises:
        HTTPException(404): If no usage record found
    """
    billing_service = BillingService(db)

    subscription = await billing_service.get_user_subscription(user.id)
    usage = await billing_service.get_current_usage(user.id)

    if not usage or not subscription:
        raise HTTPException(status_code=404, detail="No usage record found")

    return UsageResponse(
        videos_used=usage.videos_used,
        videos_limit=subscription.plan.video_limit,
        messages_used=usage.messages_used,
        messages_limit=subscription.plan.message_limit,
        period_start=usage.period_start,
        period_end=usage.period_end,
    )
