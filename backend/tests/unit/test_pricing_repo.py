"""
Unit Tests for PricingRepository

Tests for the ModelPricing repository covering all CRUD operations
and pricing versioning logic.
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.repositories.pricing_repo import PricingRepository
from app.db.models import ModelPricing


@pytest.mark.asyncio
async def test_create_pricing_per_token(db_session: AsyncSession):
    """Test creating a per_token pricing configuration."""
    repo = PricingRepository(db_session)

    pricing = await repo.create_pricing(
        provider="openrouter",
        model_name="anthropic/claude-haiku-4.5",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=5.00,
        notes="Test pricing for Claude Haiku"
    )

    assert pricing.id is not None
    assert pricing.provider == "openrouter"
    assert pricing.model_name == "anthropic/claude-haiku-4.5"
    assert pricing.pricing_type == "per_token"
    assert float(pricing.input_price_per_1m) == 1.00
    assert float(pricing.output_price_per_1m) == 5.00
    assert pricing.is_active is True
    assert pricing.notes == "Test pricing for Claude Haiku"


@pytest.mark.asyncio
async def test_create_pricing_per_request(db_session: AsyncSession):
    """Test creating a per_request pricing configuration."""
    repo = PricingRepository(db_session)

    pricing = await repo.create_pricing(
        provider="supadata",
        model_name="fetch_transcript",
        pricing_type="per_request",
        cost_per_request=0.01,
        notes="SUPADATA API call"
    )

    assert pricing.id is not None
    assert pricing.provider == "supadata"
    assert pricing.model_name == "fetch_transcript"
    assert pricing.pricing_type == "per_request"
    assert float(pricing.cost_per_request) == 0.01
    assert pricing.input_price_per_1m is None
    assert pricing.output_price_per_1m is None
    assert pricing.is_active is True


@pytest.mark.asyncio
async def test_create_pricing_with_cache_discount(db_session: AsyncSession):
    """Test creating pricing with cache discount."""
    repo = PricingRepository(db_session)

    pricing = await repo.create_pricing(
        provider="openrouter",
        model_name="google/gemini-2.5-flash",
        pricing_type="per_token",
        input_price_per_1m=0.40,
        output_price_per_1m=1.20,
        cache_discount=0.25,
        notes="Gemini Flash with caching"
    )

    assert float(pricing.cache_discount) == 0.25
    assert float(pricing.input_price_per_1m) == 0.40
    assert float(pricing.output_price_per_1m) == 1.20


@pytest.mark.asyncio
async def test_get_pricing_by_provider_and_model(db_session: AsyncSession):
    """Test retrieving active pricing by provider and model name."""
    repo = PricingRepository(db_session)

    # Create pricing
    await repo.create_pricing(
        provider="openrouter",
        model_name="anthropic/claude-haiku-4.5",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=5.00,
    )

    # Retrieve pricing
    pricing = await repo.get_pricing("openrouter", "anthropic/claude-haiku-4.5")

    assert pricing is not None
    assert pricing.provider == "openrouter"
    assert pricing.model_name == "anthropic/claude-haiku-4.5"
    assert float(pricing.input_price_per_1m) == 1.00
    assert pricing.is_active is True


@pytest.mark.asyncio
async def test_get_pricing_not_found(db_session: AsyncSession):
    """Test retrieving non-existent pricing returns None."""
    repo = PricingRepository(db_session)

    pricing = await repo.get_pricing("nonexistent", "model")

    assert pricing is None


@pytest.mark.asyncio
async def test_get_pricing_with_effective_date(db_session: AsyncSession):
    """Test retrieving pricing valid for a specific date."""
    repo = PricingRepository(db_session)

    # Create pricing with specific effective dates
    now = datetime.now(timezone.utc)
    past = now - timedelta(days=30)
    future = now + timedelta(days=30)

    pricing = await repo.create_pricing(
        provider="openrouter",
        model_name="test/model",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
    )

    # Update effective_from to past
    pricing.effective_from = past
    pricing.effective_until = future
    await db_session.commit()

    # Query with effective_date within range
    result = await repo.get_pricing("openrouter", "test/model", effective_date=now)
    assert result is not None
    assert result.id == pricing.id


@pytest.mark.asyncio
async def test_get_pricing_outside_effective_range(db_session: AsyncSession):
    """Test retrieving pricing outside effective date range returns None."""
    repo = PricingRepository(db_session)

    now = datetime.now(timezone.utc)
    past = now - timedelta(days=60)
    past_end = now - timedelta(days=30)

    pricing = await repo.create_pricing(
        provider="openrouter",
        model_name="test/model",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
    )

    # Set pricing effective in the past only
    pricing.effective_from = past
    pricing.effective_until = past_end
    await db_session.commit()

    # Query with current date (outside range)
    result = await repo.get_pricing("openrouter", "test/model", effective_date=now)
    assert result is None


@pytest.mark.asyncio
async def test_get_all_active_pricing(db_session: AsyncSession):
    """Test retrieving all active pricing configurations."""
    repo = PricingRepository(db_session)

    # Create multiple pricing configurations
    await repo.create_pricing(
        provider="openrouter",
        model_name="anthropic/claude-haiku-4.5",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=5.00,
    )

    await repo.create_pricing(
        provider="openrouter",
        model_name="google/gemini-2.5-flash",
        pricing_type="per_token",
        input_price_per_1m=0.40,
        output_price_per_1m=1.20,
    )

    await repo.create_pricing(
        provider="openai",
        model_name="text-embedding-3-small",
        pricing_type="per_token",
        input_price_per_1m=0.02,
        output_price_per_1m=0.00,
    )

    # Retrieve all active pricing
    all_pricing = await repo.get_all_active_pricing()

    assert len(all_pricing) == 3
    assert all(p.is_active for p in all_pricing)

    # Verify ordering by provider, model_name
    providers = [p.provider for p in all_pricing]
    assert providers == sorted(providers)


@pytest.mark.asyncio
async def test_get_all_active_pricing_empty(db_session: AsyncSession):
    """Test retrieving all active pricing when database is empty."""
    repo = PricingRepository(db_session)

    all_pricing = await repo.get_all_active_pricing()

    assert len(all_pricing) == 0
    assert isinstance(all_pricing, list)


@pytest.mark.asyncio
async def test_get_all_active_pricing_excludes_inactive(db_session: AsyncSession):
    """Test that get_all_active_pricing excludes inactive pricing."""
    repo = PricingRepository(db_session)

    # Create active pricing
    active = await repo.create_pricing(
        provider="openrouter",
        model_name="active/model",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
    )

    # Create inactive pricing
    inactive = await repo.create_pricing(
        provider="openrouter",
        model_name="inactive/model",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
    )

    # Deactivate the second pricing
    await repo.deactivate_pricing(inactive.id)

    # Retrieve all active pricing
    all_pricing = await repo.get_all_active_pricing()

    assert len(all_pricing) == 1
    assert all_pricing[0].id == active.id
    assert all_pricing[0].is_active is True


@pytest.mark.asyncio
async def test_deactivate_pricing(db_session: AsyncSession):
    """Test deactivating a pricing configuration."""
    repo = PricingRepository(db_session)

    # Create pricing
    pricing = await repo.create_pricing(
        provider="openrouter",
        model_name="test/model",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
    )

    assert pricing.is_active is True

    # Deactivate pricing
    deactivated = await repo.deactivate_pricing(pricing.id)

    assert deactivated is not None
    assert deactivated.id == pricing.id
    assert deactivated.is_active is False
    assert deactivated.effective_until is not None


@pytest.mark.asyncio
async def test_deactivate_pricing_with_custom_date(db_session: AsyncSession):
    """Test deactivating pricing with custom effective_until date."""
    repo = PricingRepository(db_session)

    # Create pricing
    pricing = await repo.create_pricing(
        provider="openrouter",
        model_name="test/model",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
    )

    # Deactivate with custom date
    custom_date = datetime.now(timezone.utc) + timedelta(days=7)
    deactivated = await repo.deactivate_pricing(pricing.id, effective_until=custom_date)

    assert deactivated.is_active is False
    assert deactivated.effective_until is not None
    # Allow small time difference (within 1 second)
    time_diff = abs((deactivated.effective_until - custom_date).total_seconds())
    assert time_diff < 1


@pytest.mark.asyncio
async def test_deactivate_pricing_not_found(db_session: AsyncSession):
    """Test deactivating non-existent pricing returns None."""
    repo = PricingRepository(db_session)

    result = await repo.deactivate_pricing(99999)

    assert result is None


@pytest.mark.asyncio
async def test_get_pricing_returns_most_recent_active(db_session: AsyncSession):
    """Test that get_pricing returns the most recent active pricing."""
    repo = PricingRepository(db_session)

    # Create old pricing
    old_pricing = await repo.create_pricing(
        provider="openrouter",
        model_name="test/model",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
    )

    # Update effective_from to be older
    old_pricing.effective_from = datetime.now(timezone.utc) - timedelta(days=30)
    await db_session.commit()

    # Create new pricing
    new_pricing = await repo.create_pricing(
        provider="openrouter",
        model_name="test/model",
        pricing_type="per_token",
        input_price_per_1m=1.50,
        output_price_per_1m=3.00,
    )

    # Get pricing should return the newest one
    result = await repo.get_pricing("openrouter", "test/model")

    assert result is not None
    assert result.id == new_pricing.id
    assert float(result.input_price_per_1m) == 1.50


@pytest.mark.asyncio
async def test_pricing_versioning_workflow(db_session: AsyncSession):
    """Test complete pricing versioning workflow: create, update, retrieve."""
    repo = PricingRepository(db_session)

    # Step 1: Create initial pricing
    v1 = await repo.create_pricing(
        provider="openrouter",
        model_name="test/model",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
        notes="Version 1"
    )

    # Step 2: Price changes - deactivate old, create new
    await repo.deactivate_pricing(v1.id)

    v2 = await repo.create_pricing(
        provider="openrouter",
        model_name="test/model",
        pricing_type="per_token",
        input_price_per_1m=1.50,
        output_price_per_1m=2.50,
        notes="Version 2"
    )

    # Step 3: Verify current pricing is v2
    current = await repo.get_pricing("openrouter", "test/model")
    assert current.id == v2.id
    assert float(current.input_price_per_1m) == 1.50
    assert current.notes == "Version 2"

    # Step 4: Verify v1 is inactive
    result = await db_session.execute(
        select(ModelPricing).where(ModelPricing.id == v1.id)
    )
    v1_check = result.scalar_one()
    assert v1_check.is_active is False

    # Step 5: Verify both versions exist in database
    result = await db_session.execute(
        select(func.count()).select_from(ModelPricing).where(
            ModelPricing.provider == "openrouter",
            ModelPricing.model_name == "test/model"
        )
    )
    count = result.scalar()
    assert count == 2


@pytest.mark.asyncio
async def test_unique_constraint_on_provider_model_effective_from(db_session: AsyncSession):
    """Test that unique constraint prevents duplicate pricing at same effective_from."""
    repo = PricingRepository(db_session)

    # Create first pricing
    p1 = await repo.create_pricing(
        provider="openrouter",
        model_name="test/model",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
    )

    # Try to create duplicate with same effective_from
    from sqlalchemy.exc import IntegrityError

    # Update effective_from to match
    p1.effective_from = datetime.now(timezone.utc)
    await db_session.commit()

    # Create second pricing with same provider, model, and effective_from
    p2 = ModelPricing(
        provider="openrouter",
        model_name="test/model",
        pricing_type="per_token",
        input_price_per_1m=1.50,
        output_price_per_1m=2.50,
        effective_from=p1.effective_from
    )

    db_session.add(p2)

    # Should raise IntegrityError due to unique constraint
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_create_pricing_all_fields(db_session: AsyncSession):
    """Test creating pricing with all optional fields populated."""
    repo = PricingRepository(db_session)

    pricing = await repo.create_pricing(
        provider="openrouter",
        model_name="complete/model",
        pricing_type="per_token",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
        cost_per_request=0.05,
        cache_discount=0.25,
        notes="Complete pricing configuration"
    )

    assert pricing.provider == "openrouter"
    assert pricing.model_name == "complete/model"
    assert pricing.pricing_type == "per_token"
    assert float(pricing.input_price_per_1m) == 1.00
    assert float(pricing.output_price_per_1m) == 2.00
    assert float(pricing.cost_per_request) == 0.05
    assert float(pricing.cache_discount) == 0.25
    assert pricing.notes == "Complete pricing configuration"
    assert pricing.is_active is True
    assert pricing.created_at is not None
    assert pricing.updated_at is not None
