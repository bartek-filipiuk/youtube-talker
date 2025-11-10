"""
Content Handler Node for LangGraph

Unified handler that uses intelligent search pipeline (Phase 1 + Phase 2 + Phase 3).
Routes based on smart search scores from fuzzy title matching + semantic search + LLM re-ranking.

Architecture (Updated):
- Phase 1: Query Analysis (extract title keywords, topic keywords, alternative phrasings)
- Phase 2: Smart Search (fuzzy title match + multi-query semantic search)
- Phase 3: LLM Re-ranking (re-rank results by relevance with explainability)
- Score >= 0.3: Generate content from matched videos (QA flow)
- Score < 0.3: Chitchat fallback

This eliminates need to predict user intent upfront - intelligent search guides response.
"""

from typing import Any, Dict

from loguru import logger

from app.rag.graphs.flows.chitchat_flow import compiled_chitchat_flow
from app.rag.graphs.flows.qa_flow import compiled_qa_flow
from app.rag.nodes.query_analyzer_node import analyze_query
from app.rag.nodes.smart_search_executor_node import execute_smart_search
from app.rag.nodes.result_ranker_node import rank_search_results
from app.rag.utils.state import GraphState
from app.api.websocket.messages import StatusMessage

# Configuration for content routing
CONTENT_SCORE_THRESHOLD = 0.3  # If ANY relevant content found (score >= 0.3) → generate


async def _send_status(state: GraphState, message: str, step: str) -> None:
    """
    Helper to send status message via WebSocket if available.

    Args:
        state: Current graph state (may contain websocket + connection_manager)
        message: User-friendly status message
        step: Current step (routing, retrieving, grading, generating, checking)
    """
    config = state.get("config", {})
    websocket = config.get("websocket")
    connection_manager = config.get("connection_manager")

    if websocket and connection_manager:
        try:
            await connection_manager.send_json(
                websocket,
                StatusMessage(message=message, step=step).model_dump()
            )
            logger.debug(f"Sent status: {message} (step={step})")
        except Exception as e:
            # Don't fail the whole flow if status send fails
            logger.warning(f"Failed to send status message: {e}")


async def handle_content_query(state: GraphState) -> Dict[str, Any]:
    """
    Unified content handler - replaces qa, chitchat, and metadata_search intents.

    Flow:
    1. Always perform semantic search (top_k=5)
    2. Route based on top score (two outcomes only):
       - score >= 0.4: Content found → Generate from videos (QA flow)
       - score < 0.4: No content → Chitchat response

    Args:
        state: Current graph state containing:
            - user_query: The user's input text
            - user_id: UUID string for the user
            - conversation_history: List of previous messages
            - channel_id (optional): Channel context
            - collection_name (optional): Qdrant collection

    Returns:
        Updated state with:
            - response: Generated HTML response
            - metadata: Routing decision metadata

    Example:
        # "napisz cos o mitach programowania z AI"
        # → search finds myths video (score 0.74)
        # → auto-generates summary via QA flow

        # "tell me about FastAPI"
        # → search finds videos (score 0.62)
        # → auto-generates answer from top videos

        # "hello how are you?"
        # → search finds nothing relevant (score 0.15)
        # → chitchat: "Hi! I'm here to help with your YouTube videos"
    """
    user_query = state.get("user_query", "")
    channel_id_str = state.get("channel_id")

    logger.info(
        f"Content handler processing query: '{user_query[:50]}...' "
        f"(channel={channel_id_str or 'personal'})"
    )

    try:
        # PHASE 1: Analyze query for search signals
        await _send_status(state, "Understanding your question...", "routing")
        logger.debug("Running query analyzer (Phase 1)")
        analyzer_state = await analyze_query(state)
        query_analysis = analyzer_state.get("query_analysis")

        if query_analysis:
            logger.info(
                f"[QUERY ANALYSIS] "
                f"title_keywords={query_analysis.title_keywords}, "
                f"topic_keywords={query_analysis.topic_keywords}, "
                f"intent={query_analysis.query_intent}, "
                f"confidence={query_analysis.confidence:.2f}"
            )
            logger.debug(f"[QUERY ANALYSIS] alternative_phrasings={query_analysis.alternative_phrasings}")
            logger.debug(f"[QUERY ANALYSIS] reasoning={query_analysis.reasoning}")

        # PHASE 2: Execute smart search (fuzzy title match + multi-query semantic search)
        await _send_status(state, "Finding relevant videos...", "retrieving")
        logger.debug("Running smart search executor (Phase 2)")
        search_state = await execute_smart_search(analyzer_state)
        search_results = search_state.get("search_results", [])
        search_metadata = search_state.get("metadata", {})

        # Extract top score for logging (avoid f-string format issues)
        smart_search_top_score = search_results[0].get('score', 0.0) if search_results else 0.0
        logger.info(
            f"Smart search completed: {len(search_results)} videos found, "
            f"top_score={smart_search_top_score:.3f}, "
            f"strategies={search_metadata.get('search_strategies_used', [])}"
        )

        # PHASE 3: LLM Re-ranking (only if 2+ results)
        if len(search_results) >= 2:
            await _send_status(state, "Analyzing video relevance...", "grading")
        logger.debug("Running LLM result ranker (Phase 3)")
        ranking_state = await rank_search_results(search_state)
        search_results = ranking_state.get("search_results", [])
        ranking_metadata = ranking_state.get("metadata", {})

        if ranking_metadata.get("llm_ranking_applied"):
            logger.info(
                f"LLM re-ranking applied: top LLM score={search_results[0].get('llm_relevance_score', 0.0):.3f}, "
                f"confidence={ranking_metadata.get('llm_ranking_confidence', 0.0):.2f}"
            )
            logger.debug(f"Ranking strategy: {ranking_metadata.get('llm_ranking_strategy', 'N/A')}")

        # STEP 1: Route based on top score (two outcomes only: generate or chitchat)
        top_score = search_results[0].get("score", 0.0) if search_results else 0.0

        if top_score >= CONTENT_SCORE_THRESHOLD:
            # CONTENT FOUND: Generate from videos (always generate if content exists)
            logger.info(
                f"Content found (score={top_score:.3f}) - routing to QA generation"
            )

            # Smart search already returned sorted, deduplicated results
            logger.info(f"Found {len(search_results)} relevant videos for generation")
            for idx, result in enumerate(search_results[:3], 1):
                logger.debug(
                    f"  {idx}. {result.get('title', 'N/A')[:50]} "
                    f"(score: {result['score']:.2f}, strategy: {result['strategy']})"
                )

            # Send status before generation
            await _send_status(state, "Crafting your answer...", "generating")

            # Route to QA flow for generation
            qa_state = {
                **state,
                "intent": "qa"  # QA flow will handle generation
            }
            result = await compiled_qa_flow.ainvoke(qa_state)

            # Add content handler metadata with smart search + LLM ranking info
            result["metadata"]["content_handler"] = {
                "routing_decision": "generate",
                "top_score": top_score,
                "videos_found": len(search_results),
                "search_strategies": search_metadata.get("search_strategies_used", []),
                "title_match_count": search_metadata.get("title_match_count", 0),
                "semantic_only_count": search_metadata.get("semantic_only_count", 0),
                "llm_ranking_applied": ranking_metadata.get("llm_ranking_applied", False),
                "llm_ranking_confidence": ranking_metadata.get("llm_ranking_confidence"),
                "llm_ranking_strategy": ranking_metadata.get("llm_ranking_strategy")
            }

            return result

        else:
            # NO CONTENT: Score too low → Chitchat
            logger.info(
                f"Low score (score={top_score:.3f}) - routing to chitchat"
            )

            # Send status before chitchat
            await _send_status(state, "Thinking...", "generating")

            chitchat_state = {
                **state,
                "intent": "chitchat"
            }
            result = await compiled_chitchat_flow.ainvoke(chitchat_state)

            # Add content handler metadata
            result["metadata"]["content_handler"] = {
                "routing_decision": "chitchat",
                "top_score": top_score,
                "threshold_used": "low"
            }

            return result

    except Exception as e:
        logger.exception(f"Error in content handler: {e}")

        # Fallback to chitchat on error
        try:
            await _send_status(state, "Thinking...", "generating")
            chitchat_state = {
                **state,
                "intent": "chitchat"
            }
            result = await compiled_chitchat_flow.ainvoke(chitchat_state)
            result["metadata"]["content_handler_error"] = str(e)
            return result
        except Exception as fallback_error:
            logger.exception(f"Chitchat fallback also failed: {fallback_error}")
            return {
                **state,
                "response": "<p>Sorry, I encountered an error processing your request. Please try again.</p>",
                "metadata": {
                    **(state.get("metadata", {})),
                    "response_type": "error",
                    "error": str(e),
                    "fallback_error": str(fallback_error)
                }
            }
