"""
Pricing Repository

Database operations for ModelPricing model.
"""

from typing import Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelPricing
from app.db.repositories.base import BaseRepository


class PricingRepository(BaseRepository[ModelPricing]):
    """Repository for ModelPricing model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(ModelPricing, session)

    async def get_pricing(
        self,
        provider: str,
        model_name: str,
        effective_date: Optional[datetime] = None,
    ) -> Optional[ModelPricing]:
        """
        Get active pricing for a specific model.

        Args:
            provider: Provider name (e.g., 'openrouter', 'openai', 'supadata')
            model_name: Model identifier (e.g., 'anthropic/claude-3.5-haiku')
            effective_date: Date to check pricing for (defaults to NOW)

        Returns:
            ModelPricing instance or None if not found

        Example:
            pricing = await repo.get_pricing('openrouter', 'anthropic/claude-3.5-haiku')
            if pricing:
                cost = (tokens / 1_000_000) * pricing.input_price_per_1m
        """
        query = select(ModelPricing).where(
            ModelPricing.provider == provider,
            ModelPricing.model_name == model_name,
            ModelPricing.is_active == True,  # noqa: E712
        )

        if effective_date:
            # Find pricing valid for the specified date
            query = query.where(
                ModelPricing.effective_from <= effective_date,
                (ModelPricing.effective_until.is_(None))
                | (ModelPricing.effective_until > effective_date),
            )
        else:
            # Get most recent active pricing
            query = query.order_by(ModelPricing.effective_from.desc()).limit(1)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_active_pricing(self) -> list[ModelPricing]:
        """
        Get all currently active pricing configurations.

        Returns:
            List of active ModelPricing instances

        Useful for:
            - Validating that all used models have pricing configured
            - Generating pricing reports
            - Admin dashboard
        """
        query = select(ModelPricing).where(
            ModelPricing.is_active == True  # noqa: E712
        ).order_by(ModelPricing.provider, ModelPricing.model_name)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def deactivate_pricing(
        self,
        pricing_id: int,
        effective_until: Optional[datetime] = None,
    ) -> Optional[ModelPricing]:
        """
        Deactivate a pricing configuration.

        Args:
            pricing_id: ID of the pricing to deactivate
            effective_until: Date when pricing becomes inactive (defaults to NOW)

        Returns:
            Updated ModelPricing instance or None if not found
        """
        # Get pricing by ID (ModelPricing uses int, not UUID)
        result = await self.session.execute(
            select(ModelPricing).where(ModelPricing.id == pricing_id)
        )
        pricing = result.scalar_one_or_none()

        if not pricing:
            return None

        pricing.is_active = False
        pricing.effective_until = effective_until or datetime.now()

        await self.session.commit()
        await self.session.refresh(pricing)

        return pricing

    async def create_pricing(
        self,
        provider: str,
        model_name: str,
        pricing_type: str,
        input_price_per_1m: Optional[float] = None,
        output_price_per_1m: Optional[float] = None,
        cost_per_request: Optional[float] = None,
        cache_discount: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> ModelPricing:
        """
        Create new pricing configuration.

        Args:
            provider: Provider name
            model_name: Model identifier
            pricing_type: 'per_token', 'per_request', or 'credit_based'
            input_price_per_1m: Cost per 1M input tokens (for per_token type)
            output_price_per_1m: Cost per 1M output tokens (for per_token type)
            cost_per_request: Fixed cost per request (for per_request type)
            cache_discount: Multiplier for cached tokens (e.g., 0.25)
            notes: Optional description

        Returns:
            Created ModelPricing instance
        """
        pricing = ModelPricing(
            provider=provider,
            model_name=model_name,
            pricing_type=pricing_type,
            input_price_per_1m=input_price_per_1m,
            output_price_per_1m=output_price_per_1m,
            cost_per_request=cost_per_request,
            cache_discount=cache_discount,
            notes=notes,
        )

        self.session.add(pricing)
        await self.session.commit()
        await self.session.refresh(pricing)

        return pricing
