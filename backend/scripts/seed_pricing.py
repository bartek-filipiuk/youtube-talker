"""
Seed Pricing Script

Populates the model_pricing table with default pricing configurations for all AI models.
Run this script after database migrations to initialize pricing data.

Usage:
    python scripts/seed_pricing.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.db.repositories.pricing_repo import PricingRepository


async def seed_pricing():
    """
    Seed the model_pricing table with current pricing for all AI models.

    Pricing data based on public pricing pages (as of 2025-01):
    - OpenRouter: https://openrouter.ai/models
    - OpenAI: https://platform.openai.com/docs/pricing
    - SUPADATA: Fixed cost per request

    Run this script:
    - After initial database setup
    - When model pricing changes (will create new versioned entries)
    """

    # Create async session
    async with AsyncSessionLocal() as db:
        repo = PricingRepository(db)

        # Define pricing configurations
        pricing_configs = [
            # OpenRouter - Claude Haiku 4.5
            {
                "provider": "openrouter",
                "model_name": "anthropic/claude-haiku-4.5",
                "pricing_type": "per_token",
                "input_price_per_1m": 1.00,  # $1.00 per 1M input tokens
                "output_price_per_1m": 5.00,  # $5.00 per 1M output tokens
                "notes": "Claude Haiku 4.5 via OpenRouter - text generation, Q&A, content creation",
            },
            # OpenRouter - Gemini Flash 2.5
            {
                "provider": "openrouter",
                "model_name": "google/gemini-2.5-flash",
                "pricing_type": "per_token",
                "input_price_per_1m": 0.40,  # $0.40 per 1M input tokens
                "output_price_per_1m": 1.20,  # $1.20 per 1M output tokens
                "cache_discount": 0.25,  # 75% discount on cached tokens
                "notes": "Gemini Flash 2.5 via OpenRouter - structured JSON output, intent classification, chunk grading",
            },
            # OpenAI - Embeddings
            {
                "provider": "openai",
                "model_name": "text-embedding-3-small",
                "pricing_type": "per_token",
                "input_price_per_1m": 0.02,  # $0.02 per 1M tokens
                "output_price_per_1m": 0.00,  # Embeddings only use input
                "notes": "OpenAI text-embedding-3-small (1536-dim) - semantic search and RAG retrieval",
            },
            # SUPADATA - Transcript Fetching
            {
                "provider": "supadata",
                "model_name": "fetch_transcript",
                "pricing_type": "per_request",
                "cost_per_request": 0.01,  # $0.01 per API call
                "notes": "SUPADATA transcript fetch - fixed cost per YouTube video",
            },
            # OpenRouter - Grok 4 Fast
            {
                "provider": "openrouter",
                "model_name": "x-ai/grok-4-fast",
                "pricing_type": "per_token",
                "input_price_per_1m": 0.20,  # $0.20 per 1M input tokens
                "output_price_per_1m": 0.50,  # $0.50 per 1M output tokens
                "cache_discount": 0.25,  # 75% discount on cached tokens ($0.05)
                "notes": "Grok 4 Fast via OpenRouter - 2M context window, fast inference",
            },
            # OpenRouter - Kimi K2 Thinking
            {
                "provider": "openrouter",
                "model_name": "moonshotai/kimi-k2-thinking",
                "pricing_type": "per_token",
                "input_price_per_1m": 0.55,  # $0.55 per 1M input tokens
                "output_price_per_1m": 2.25,  # $2.25 per 1M output tokens
                "notes": "Kimi K2 Thinking via OpenRouter - deep reasoning model",
            },
        ]

        print("🌱 Seeding model_pricing table...")
        print(f"   Found {len(pricing_configs)} pricing configurations to insert")
        print()

        created_count = 0
        updated_count = 0

        for config in pricing_configs:
            provider = config["provider"]
            model_name = config["model_name"]

            # Check if pricing already exists
            existing = await repo.get_pricing(provider, model_name)

            if existing:
                # Pricing exists - check if it matches current config
                needs_update = False

                if config.get("input_price_per_1m") != existing.input_price_per_1m:
                    needs_update = True
                if config.get("output_price_per_1m") != existing.output_price_per_1m:
                    needs_update = True
                if config.get("cost_per_request") != existing.cost_per_request:
                    needs_update = True

                if needs_update:
                    print(
                        f"   ⚠️  Pricing changed for {provider}/{model_name}"
                    )
                    print(f"       Deactivating old pricing (id={existing.id})")

                    # Deactivate old pricing
                    await repo.deactivate_pricing(existing.id)

                    # Create new pricing version
                    new_pricing = await repo.create_pricing(**config)
                    print(f"       ✅ Created new pricing version (id={new_pricing.id})")
                    updated_count += 1
                else:
                    print(
                        f"   ✓ {provider}/{model_name} - already configured"
                    )
            else:
                # Create new pricing
                pricing = await repo.create_pricing(**config)
                print(
                    f"   ✅ Created {provider}/{model_name} (id={pricing.id})"
                )
                created_count += 1

        print()
        print(f"✨ Seeding complete!")
        print(f"   Created: {created_count} new pricing configurations")
        print(f"   Updated: {updated_count} pricing configurations")
        print()

        # Verify all active pricing
        all_pricing = await repo.get_all_active_pricing()
        print(f"📊 Active pricing configurations: {len(all_pricing)}")
        print()
        print("Provider       | Model Name                     | Type        | Input ($/1M) | Output ($/1M) | Per Request ($)")
        print("-" * 120)

        for p in all_pricing:
            provider = p.provider.ljust(14)
            model = p.model_name.ljust(30)
            pricing_type = p.pricing_type.ljust(11)
            input_price = f"${p.input_price_per_1m:.2f}" if p.input_price_per_1m else "N/A"
            output_price = f"${p.output_price_per_1m:.2f}" if p.output_price_per_1m else "N/A"
            per_request = f"${p.cost_per_request:.2f}" if p.cost_per_request else "N/A"

            print(
                f"{provider} | {model} | {pricing_type} | {input_price:12} | {output_price:13} | {per_request:16}"
            )

        print()


if __name__ == "__main__":
    print("=" * 60)
    print("YoutubeTalker - Seed Model Pricing")
    print("=" * 60)
    print()

    try:
        asyncio.run(seed_pricing())
        print("✅ Pricing seeding successful!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error seeding pricing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
