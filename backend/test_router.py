"""
Quick script to test intent classification with Claude Haiku 4.5
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.rag.nodes.router_node import classify_intent
from app.rag.utils.state import GraphState


async def test_intent(query: str, expected_intent: str = None):
    """Test a single query"""
    print(f"\n{'='*80}")
    print(f"Query: {query}")
    print(f"Expected: {expected_intent or 'TBD'}")
    print(f"-"*80)

    state = GraphState(
        user_query=query,
        user_id="test-user-123",
        conversation_history=[],
        channel_name=None
    )

    try:
        result = await classify_intent(state)
        intent = result.get("intent")
        metadata = result.get("metadata", {})
        confidence = metadata.get("intent_confidence", 0)
        reasoning = metadata.get("intent_reasoning", "")

        match = "✅ PASS" if intent == expected_intent else "❌ FAIL"
        if not expected_intent:
            match = "📝 RECORD"

        print(f"Actual Intent: {intent}")
        print(f"Confidence: {confidence:.2f}")
        print(f"Reasoning: {reasoning}")
        print(f"Result: {match}")

        return {
            "query": query,
            "expected": expected_intent,
            "actual": intent,
            "confidence": confidence,
            "reasoning": reasoning,
            "pass": intent == expected_intent if expected_intent else None
        }
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            "query": query,
            "expected": expected_intent,
            "actual": "ERROR",
            "confidence": 0,
            "reasoning": str(e),
            "pass": False
        }


async def main():
    """Run test suite"""
    print("\n" + "="*80)
    print("INTENT CLASSIFICATION TEST - Claude Haiku 4.5")
    print("="*80)

    tests = [
        # === BASIC BOUNDARY CASES ===
        ("what movies we have here?", "metadata"),
        ("show me videos", "metadata"),
        ("what is FastAPI?", "qa"),
        ("tell me about FastAPI", "qa"),
        ("find videos about Python", "metadata_search"),
        ("list all videos", "metadata"),

        # === PARTIAL TITLE MATCHING ===
        ("give me a summary of Cursor Setup", "metadata_search_and_summarize"),  # Partial title
        ("tell me about the Cursor video", "metadata_search_and_summarize"),  # Generic reference
        ("what does the 10x Better video say?", "metadata_search_and_summarize"),  # Partial title from end
        ("summarize the video about cursor", "metadata_search_and_summarize"),  # Topic-based

        # === EXACT TITLE (KNOWN REGRESSION) ===
        ("tell me something about This Cursor Setup Changes Everything (10x Better) - one paragraph", "qa"),
        ("summarize This Cursor Setup Changes Everything (10x Better)", "qa"),  # Exact title, command form
        ("what does This Cursor Setup Changes Everything (10x Better) cover?", "qa"),  # Exact title, question form

        # === COMPLEX QUESTION PHRASINGS ===
        ("give me the main points from the cursor video", "metadata_search_and_summarize"),
        ("what are the key takeaways about cursor setup?", "qa"),  # Could be topic or specific video
        ("explain what the video says about cursor configuration", "metadata_search_and_summarize"),
        ("break down the cursor setup tutorial for me", "metadata_search_and_summarize"),

        # === COMPOUND INTENTS ===
        ("Show me videos about Python and explain the first one", "metadata_search_and_summarize"),
        ("Find the FastAPI video and create a LinkedIn post about it", "linkedin"),  # Two-step, should prioritize first step
        ("List all videos and tell me which one is best", "metadata"),  # List first, opinion later

        # === CONTEXT-DEPENDENT (WOULD FAIL WITHOUT CONTEXT) ===
        # These should still classify correctly even without prior context
        ("explain the first video", "qa"),  # Assumes context exists
        ("tell me more about it", "qa"),  # Pronoun reference
        ("what else does it cover?", "qa"),  # Continuation

        # === TYPOS & INFORMAL ===
        ("waht vidoes do I hav?", "metadata"),
        ("wut is fastapi?", "qa"),
        ("gimme a summary of da cursor vid", "metadata_search_and_summarize"),
        ("yo what does this channel got?", "metadata"),

        # === EDGE CASES ===
        ("", "chitchat"),  # Empty query
        ("hello", "chitchat"),  # Greeting
        ("thanks", "chitchat"),  # Gratitude
        ("create a linkedin post about cursor setup best practices", "linkedin"),  # LinkedIn intent
    ]

    results = []
    for query, expected in tests:
        result = await test_intent(query, expected)
        results.append(result)
        await asyncio.sleep(0.5)  # Rate limit

    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")

    passed = sum(1 for r in results if r["pass"] is True)
    failed = sum(1 for r in results if r["pass"] is False)
    total = len([r for r in results if r["pass"] is not None])

    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")

    if failed > 0:
        print(f"\n❌ FAILED TESTS:")
        for r in results:
            if r["pass"] is False:
                print(f"  - {r['query'][:50]}")
                print(f"    Expected: {r['expected']}, Got: {r['actual']}")


if __name__ == "__main__":
    asyncio.run(main())
