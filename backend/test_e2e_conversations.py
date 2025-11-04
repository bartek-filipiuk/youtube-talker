"""
End-to-End Conversation Testing

Tests complete conversation flows with real responses.
Evaluates response quality, not just intent classification.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from app.rag.graphs.router import run_graph
from app.db.repositories.channel_video_repo import ChannelVideoRepository
from app.db.session import AsyncSessionLocal


# Test scenarios with expected behavior
TEST_CONVERSATIONS = [
    {
        "category": "Exact Title Recognition",
        "query": "tell me something about This Cursor Setup Changes Everything (10x Better) - one paragraph",
        "expected_intent": "qa",
        "expected_behavior": "Should directly answer from video content without asking to search"
    },
    {
        "category": "Exact Title Recognition",
        "query": "summarize This Cursor Setup Changes Everything (10x Better)",
        "expected_intent": "qa",
        "expected_behavior": "Should provide summary directly"
    },
    {
        "category": "Partial Title Search",
        "query": "give me a summary of Cursor Setup",
        "expected_intent": "metadata_search_and_summarize",
        "expected_behavior": "Should find video and ask what to know about it"
    },
    {
        "category": "List All Videos",
        "query": "what videos do we have here?",
        "expected_intent": "metadata",
        "expected_behavior": "Should list all channel videos"
    },
    {
        "category": "Search by Topic",
        "query": "find videos about cursor",
        "expected_intent": "metadata_search",
        "expected_behavior": "Should search and return matching videos"
    },
    {
        "category": "Question about Content",
        "query": "what are the main tips for cursor setup?",
        "expected_intent": "qa",
        "expected_behavior": "Should retrieve and answer from video content"
    },
    {
        "category": "Compound Intent",
        "query": "Show me videos about cursor and explain what they cover",
        "expected_intent": "metadata_search_and_summarize",
        "expected_behavior": "Should find videos and provide guidance on next steps"
    },
    {
        "category": "LinkedIn Priority",
        "query": "Find the cursor video and create a LinkedIn post about it",
        "expected_intent": "linkedin",
        "expected_behavior": "Should prioritize LinkedIn post creation"
    },
    {
        "category": "Generic Reference (Context)",
        "query": "explain what the video says about cursor configuration",
        "expected_intent": "qa",
        "expected_behavior": "Should assume context exists and answer"
    },
    {
        "category": "Informal Language",
        "query": "yo what does this channel got?",
        "expected_intent": "metadata",
        "expected_behavior": "Should handle informal tone and list videos"
    },
]


async def get_channel_context():
    """Get test-channel context"""
    async with AsyncSessionLocal() as session:
        channel_repo = ChannelVideoRepository(session)

        # Get test-channel info
        from app.db.repositories.channel_repo import ChannelRepository
        channel_repo_obj = ChannelRepository(session)
        channel = await channel_repo_obj.get_by_name("test-channel")

        if not channel:
            return None, None, None

        return str(channel.id), channel.qdrant_collection_name, channel.name


async def test_conversation(scenario: dict, channel_id: str, collection_name: str):
    """Test a single conversation"""
    query = scenario["query"]
    expected_intent = scenario["expected_intent"]
    category = scenario["category"]

    print(f"\n{'='*100}")
    print(f"CATEGORY: {category}")
    print(f"{'='*100}")
    print(f"User Query: {query}")
    print(f"Expected Intent: {expected_intent}")
    print(f"Expected Behavior: {scenario['expected_behavior']}")
    print(f"-"*100)

    try:
        # Run the graph with channel context
        # Use a proper UUID for user_id
        from uuid import uuid4
        test_user_id = str(uuid4())

        result = await run_graph(
            user_query=query,
            user_id=test_user_id,
            conversation_history=[],
            config={
                "channel_id": channel_id,
                "collection_name": collection_name
            }
        )

        actual_intent = result.get("intent", "unknown")
        confidence = result.get("metadata", {}).get("intent_confidence", 0)
        reasoning = result.get("metadata", {}).get("intent_reasoning", "")
        response = result.get("response", "")

        # Evaluate intent match
        intent_match = "✅ PASS" if actual_intent == expected_intent else "❌ FAIL"

        print(f"\n📊 CLASSIFICATION RESULTS:")
        print(f"  Actual Intent: {actual_intent}")
        print(f"  Confidence: {confidence:.2f}")
        print(f"  Reasoning: {reasoning}")
        print(f"  Intent Match: {intent_match}")

        print(f"\n💬 RESPONSE:")
        print(f"  Length: {len(response)} characters")

        # Show first 500 chars of response (cleaned HTML for readability)
        response_preview = response[:500]
        if "<p>" in response_preview:
            # Extract text from HTML for preview
            import re
            text_preview = re.sub('<[^<]+?>', '', response_preview)
            print(f"  Preview: {text_preview}...")
        else:
            print(f"  Preview: {response_preview}...")

        # Evaluate response quality
        print(f"\n🔍 RESPONSE QUALITY EVALUATION:")

        # Check for error messages
        has_error = "error" in response.lower() or "something went wrong" in response.lower()
        print(f"  Has Error: {'❌ YES' if has_error else '✅ NO'}")

        # Check for appropriate content
        if actual_intent == "metadata":
            has_video_list = "<ol>" in response or "<li>" in response
            print(f"  Has Video List: {'✅ YES' if has_video_list else '❌ NO'}")

        elif actual_intent == "metadata_search":
            has_results = "found" in response.lower() or "matching" in response.lower()
            print(f"  Has Search Results: {'✅ YES' if has_results else '❌ NO'}")

        elif actual_intent == "metadata_search_and_summarize":
            has_guidance = "ask" in response.lower() or "know" in response.lower()
            print(f"  Has CTA/Guidance: {'✅ YES' if has_guidance else '❌ NO'}")

        elif actual_intent == "qa":
            has_content = len(response) > 200  # QA should have substantial content
            print(f"  Has Substantial Content: {'✅ YES' if has_content else '❌ NO'}")

        elif actual_intent == "linkedin":
            has_linkedin_content = "linkedin" in response.lower()
            print(f"  LinkedIn Related: {'✅ YES' if has_linkedin_content else '❌ NO'}")

        # Overall assessment
        print(f"\n📝 OVERALL ASSESSMENT:")
        if intent_match == "✅ PASS" and not has_error:
            print(f"  Status: ✅ SUCCESS - Intent correct, response generated")
        elif intent_match == "✅ PASS" and has_error:
            print(f"  Status: ⚠️ PARTIAL - Intent correct but response has errors")
        else:
            print(f"  Status: ❌ FAIL - Wrong intent classification")

        return {
            "category": category,
            "query": query,
            "expected_intent": expected_intent,
            "actual_intent": actual_intent,
            "confidence": confidence,
            "reasoning": reasoning,
            "response_preview": response[:300],
            "full_response": response,
            "intent_match": intent_match == "✅ PASS",
            "has_error": has_error,
            "response_length": len(response)
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

        return {
            "category": category,
            "query": query,
            "expected_intent": expected_intent,
            "actual_intent": "ERROR",
            "confidence": 0,
            "reasoning": str(e),
            "response_preview": "",
            "full_response": "",
            "intent_match": False,
            "has_error": True,
            "response_length": 0
        }


async def main():
    """Run all conversation tests"""
    print("\n" + "="*100)
    print("END-TO-END CONVERSATION TESTING")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)

    # Get channel context
    print("\n📡 Getting test-channel context...")
    channel_id, collection_name, channel_name = await get_channel_context()

    if not channel_id:
        print("❌ ERROR: test-channel not found!")
        print("Please ensure test-channel exists in the database")
        return

    print(f"✅ Found channel: {channel_name}")
    print(f"   Channel ID: {channel_id}")
    print(f"   Collection: {collection_name}")

    # Run all tests
    results = []
    for scenario in TEST_CONVERSATIONS:
        result = await test_conversation(scenario, channel_id, collection_name)
        results.append(result)
        await asyncio.sleep(1)  # Rate limit between tests

    # Summary
    print(f"\n\n{'='*100}")
    print("TEST SUMMARY")
    print(f"{'='*100}")

    total = len(results)
    intent_correct = sum(1 for r in results if r["intent_match"])
    no_errors = sum(1 for r in results if not r["has_error"])

    print(f"\n📊 STATISTICS:")
    print(f"  Total Tests: {total}")
    print(f"  Intent Correct: {intent_correct}/{total} ({intent_correct/total*100:.1f}%)")
    print(f"  No Errors: {no_errors}/{total} ({no_errors/total*100:.1f}%)")

    # Group by category
    print(f"\n📁 RESULTS BY CATEGORY:")
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    for cat, cat_results in categories.items():
        correct = sum(1 for r in cat_results if r["intent_match"])
        print(f"  {cat}: {correct}/{len(cat_results)} correct")

    # Failed tests
    failed = [r for r in results if not r["intent_match"]]
    if failed:
        print(f"\n❌ FAILED TESTS ({len(failed)}):")
        for r in failed:
            print(f"  - {r['query'][:60]}...")
            print(f"    Expected: {r['expected_intent']}, Got: {r['actual_intent']}")

    return results


if __name__ == "__main__":
    results = asyncio.run(main())
