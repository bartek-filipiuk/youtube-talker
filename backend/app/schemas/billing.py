"""
Billing Schemas

Pydantic models for billing API requests and responses.
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Type alias for billing cycle
BillingCycle = Literal["monthly", "annual"]


# ============ Request Schemas ============


class CheckoutRequest(BaseModel):
    """Request to create a Stripe Checkout session."""

    plan_id: UUID = Field(..., description="Subscription plan UUID")
    billing_cycle: BillingCycle = Field(..., description="Billing cycle: 'monthly' or 'annual'")


class PortalRequest(BaseModel):
    """Request to create a Stripe Customer Portal session."""

    return_url: Optional[str] = Field(None, description="URL to redirect after leaving portal")


# ============ Response Schemas ============


class PlanResponse(BaseModel):
    """Subscription plan details."""

    id: UUID
    name: str
    display_name: str
    monthly_price_cents: int
    annual_price_cents: Optional[int]
    video_limit: Optional[int]
    message_limit: Optional[int]
    features: dict

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    """User subscription details."""

    id: UUID
    plan: PlanResponse
    status: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool
    trial_end: Optional[datetime]

    class Config:
        from_attributes = True


class UsageResponse(BaseModel):
    """Current period usage details."""

    videos_used: int
    videos_limit: Optional[int]  # None = unlimited
    messages_used: int
    messages_limit: Optional[int]  # None = unlimited
    period_start: datetime
    period_end: datetime


class CheckoutResponse(BaseModel):
    """Response from checkout session creation."""

    checkout_url: str
    session_id: str


class PortalResponse(BaseModel):
    """Response from portal session creation."""

    portal_url: str


class BillingStatusResponse(BaseModel):
    """Combined billing status with subscription and usage."""

    subscription: Optional[SubscriptionResponse]
    usage: Optional[UsageResponse]
    is_pro: bool
    is_trialing: bool
    is_canceled: bool


class PlansListResponse(BaseModel):
    """List of available subscription plans."""

    plans: list[PlanResponse]
