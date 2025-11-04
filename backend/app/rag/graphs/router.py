"""
Main Router for LangGraph Flows

Orchestrates intent classification and routing to appropriate flow.
Entry point for all RAG operations.
"""

from loguru import logger
from typing import Dict, Any

from app.rag.utils.state import GraphState
from app.rag.nodes.router_node import classify_intent
from app.rag.graphs.flows.chitchat_flow import compiled_chitchat_flow
from app.rag.graphs.flows.qa_flow import compiled_qa_flow
from app.rag.graphs.flows.linkedin_flow import compiled_linkedin_flow
from app.rag.graphs.flows.metadata_flow import compiled_metadata_flow
from app.rag.graphs.flows.metadata_search_flow import compiled_metadata_search_flow
from app.rag.graphs.flows.video_load_flow import compiled_video_load_flow
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService
from collections import defaultdict
import os

# Configuration for proactive search fallback
FALLBACK_SCORE_THRESHOLD = 0.75  # Cosine similarity threshold for strong match
FALLBACK_CONFIDENCE_THRESHOLD = 0.85  # Intent confidence threshold to trigger fallback
FALLBACK_TOP_K = 5  # Quick search limit
ENABLE_PROACTIVE_FALLBACK = os.getenv("ENABLE_PROACTIVE_FALLBACK", "true").lower() == "true"


async def proactive_search_fallback(state: GraphState) -> GraphState:
    """
    Proactive search fallback to catch router misclassifications.

    Runs a quick semantic search after intent classification but before routing.
    If strong matches found (score > 0.75), overrides intent to metadata_search_and_summarize.

    This catches edge cases where router misclassifies topic-based queries as chitchat/qa
    when they should search for specific videos (e.g., "napisz cos o mitach programowania z AI").

    Trigger conditions (runs fallback if ANY true):
    - Intent confidence < 0.85 (low confidence classification)
    - Intent == "chitchat" (might be topic-based query misclassified)
    - Intent == "qa" with short conversation history (no clear context established)

    Args:
        state: Current graph state with intent already classified

    Returns:
        Updated state with potentially overridden intent and fallback metadata
    """
    # Check feature flag
    if not ENABLE_PROACTIVE_FALLBACK:
        logger.debug("Proactive fallback disabled via config")
        return state

    # Extract state info
    user_query = state.get("user_query", "")
    user_id_str = state.get("user_id", "")
    intent = state.get("intent", "")
    confidence = state.get("metadata", {}).get("intent_confidence", 1.0)
    conversation_history = state.get("conversation_history", [])

    # Check if fallback should trigger
    should_fallback = (
        confidence < FALLBACK_CONFIDENCE_THRESHOLD or
        intent == "chitchat" or
        (intent == "qa" and len(conversation_history) < 2)
    )

    if not should_fallback:
        logger.debug(
            f"Skipping proactive fallback (intent={intent}, "
            f"confidence={confidence:.2f}, history_len={len(conversation_history)})"
        )
        return state

    logger.info(
        f"Triggering proactive search fallback (intent={intent}, "
        f"confidence={confidence:.2f}, query: {user_query[:50]}...)"
    )

    try:
        # Step 1: Generate embedding for query
        embedding_service = EmbeddingService()
        embeddings = await embedding_service.generate_embeddings([user_query], user_id=user_id_str)
        query_vector = embeddings[0]

        # Step 2: Quick semantic search (conditional based on context)
        qdrant_service = QdrantService()
        channel_id_str = state.get("channel_id")
        collection_name = state.get("collection_name")

        if channel_id_str and collection_name:
            # Channel context
            logger.debug(f"Fallback searching channel collection: {collection_name}")
            results = await qdrant_service.search(
                query_vector=query_vector,
                user_id=user_id_str,
                channel_id=channel_id_str,
                collection_name=collection_name,
                top_k=FALLBACK_TOP_K
            )
        else:
            # Personal context
            logger.debug(f"Fallback searching user collection: {user_id_str}")
            results = await qdrant_service.search(
                query_vector=query_vector,
                user_id=user_id_str,
                top_k=FALLBACK_TOP_K
            )

        if not results:
            logger.info("Proactive fallback: No results found, keeping original intent")
            return state

        # Step 3: Check for strong matches (score > threshold)
        top_score = results[0].get("score", 0.0) if results else 0.0

        if top_score < FALLBACK_SCORE_THRESHOLD:
            logger.info(
                f"Proactive fallback: Top score {top_score:.3f} below threshold "
                f"{FALLBACK_SCORE_THRESHOLD}, keeping original intent"
            )
            return state

        # Step 4: Strong match found - override intent and extract video IDs
        logger.info(
            f"Proactive fallback: Strong match found (score={top_score:.3f}), "
            f"overriding intent to metadata_search_and_summarize"
        )

        # Group results by video ID and calculate average scores
        video_scores = defaultdict(list)
        for result in results:
            payload = result.get("payload", {})
            youtube_video_id = payload.get("youtube_video_id")
            score = result.get("score", 0.0)

            if youtube_video_id and score >= FALLBACK_SCORE_THRESHOLD:
                video_scores[youtube_video_id].append(score)

        # Calculate average score per video
        video_avg_scores = {
            video_id: sum(scores) / len(scores)
            for video_id, scores in video_scores.items()
        }

        # Sort by score and get top video IDs
        sorted_video_ids = sorted(
            video_avg_scores.keys(),
            key=lambda vid: video_avg_scores[vid],
            reverse=True
        )

        logger.info(f"Proactive fallback found {len(sorted_video_ids)} relevant videos")

        # Update state with override
        original_intent = intent
        metadata = state.get("metadata", {})

        return {
            **state,
            "intent": "metadata_search_and_summarize",
            "fallback_video_ids": sorted_video_ids,  # Pass to video_search_node for reuse
            "fallback_video_scores": video_avg_scores,
            "metadata": {
                **metadata,
                "fallback_triggered": True,
                "fallback_override": True,
                "original_intent_before_override": original_intent,
                "fallback_top_score": top_score,
                "fallback_video_count": len(sorted_video_ids)
            }
        }

    except Exception as e:
        logger.exception(f"Error in proactive search fallback: {e}")
        # On error, return original state (graceful degradation)
        return state


async def run_graph(
    user_query: str,
    user_id: str,
    conversation_history: list,
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Main entry point for RAG system.

    Orchestrates the complete flow:
    1. Classify user intent (router node)
    2. Route to appropriate flow (chitchat, qa, linkedin, metadata, metadata_search, or video_load)
    3. Return final state with response

    Args:
        user_query: The user's input text
        user_id: User identifier for personalization
        conversation_history: List of previous messages for context
        config: Optional runtime configuration (loaded from ConfigService)

    Returns:
        Final GraphState containing:
            - user_query: Original query
            - user_id: User identifier
            - conversation_history: Conversation context
            - intent: Classified intent ("chitchat", "qa", "linkedin", "metadata", "metadata_search", or "video_load")
            - response: Generated response (HTML formatted)
            - metadata: Response metadata including:
                - intent_confidence: Router confidence score
                - intent_reasoning: Router reasoning
                - response_type: Type of response generated
                - chunks_used: Number of RAG chunks used (0 for chitchat)
                - source_chunks: List of chunk IDs used (if applicable)

    Raises:
        ValueError: If intent classification fails or returns unknown intent
        Exception: If any flow execution fails

    Example:
        result = await run_graph(
            user_query="What is FastAPI?",
            user_id="user123",
            conversation_history=[],
            config={"top_k": 12}
        )
        print(result["response"])  # "<p>FastAPI is...</p>"
        print(result["intent"])     # "qa"
        print(result["metadata"]["chunks_used"])  # 5
    """
    # Initialize state
    config = config or {}
    state: GraphState = {
        "user_query": user_query,
        "user_id": user_id,
        "conversation_history": conversation_history,
        "config": config
    }

    # Extract channel info from config if present
    if "channel_id" in config:
        state["channel_id"] = config["channel_id"]
    if "collection_name" in config:
        state["collection_name"] = config["collection_name"]

    logger.info(f"Starting RAG flow for user {user_id}: {user_query[:50]}...")

    # Step 1: Classify intent
    state = await classify_intent(state)
    intent = state.get("intent")

    if not intent:
        raise ValueError("Intent classification failed - no intent returned")

    # Validate intent is recognized
    VALID_INTENTS = {
        "chitchat", "qa", "linkedin", "metadata",
        "metadata_search", "metadata_search_and_summarize", "video_load"
    }

    if intent not in VALID_INTENTS:
        logger.error(
            f"Invalid intent '{intent}' returned by LLM. "
            f"Valid intents: {VALID_INTENTS}. "
            f"Defaulting to chitchat flow."
        )
        # Store original invalid intent for debugging
        original_intent = intent
        intent = "chitchat"
        state["intent"] = "chitchat"

        # Add error metadata
        metadata = state.get("metadata", {})
        metadata["intent_error"] = True
        metadata["original_invalid_intent"] = original_intent
        state["metadata"] = metadata

    logger.info(f"Intent classified as '{intent}' with confidence {state.get('metadata', {}).get('intent_confidence', 0):.2f}")

    # Step 1.5: Run proactive search fallback (if enabled and conditions met)
    state = await proactive_search_fallback(state)
    intent = state.get("intent")  # Update intent in case fallback overrode it

    # Step 2: Route to appropriate flow
    if intent == "chitchat":
        result = await compiled_chitchat_flow.ainvoke(state)
    elif intent == "qa":
        result = await compiled_qa_flow.ainvoke(state)
    elif intent == "linkedin":
        result = await compiled_linkedin_flow.ainvoke(state)
    elif intent == "metadata":
        result = await compiled_metadata_flow.ainvoke(state)
    elif intent == "metadata_search":
        result = await compiled_metadata_search_flow.ainvoke(state)
    elif intent == "metadata_search_and_summarize":
        # TWO-STAGE FLOW: Find video → Auto-summarize
        logger.info("Executing compound flow: metadata_search → qa (auto-summarize)")

        # STAGE 1: Find the video(s)
        search_result = await compiled_metadata_search_flow.ainvoke(state)

        # Check if any videos were found
        video_count = search_result.get("metadata", {}).get("video_count", 0)

        if video_count >= 1:
            # Videos found - auto-generate summary
            logger.info(
                f"Found {video_count} video(s) - auto-generating summary via QA flow "
                f"(will retrieve from top-scoring videos)"
            )

            # STAGE 2: Auto-generate summary using QA flow
            # The QA retrieval will naturally favor highest-scoring videos
            qa_state = {
                **search_result,
                "user_query": "Summarize the main points and key information from this video" if video_count == 1 else "Summarize the main points from the most relevant video about this topic",
                "intent": "qa"  # Override to qa for generation
            }
            result = await compiled_qa_flow.ainvoke(qa_state)

            # Preserve original search metadata
            result["metadata"]["original_intent"] = "metadata_search_and_summarize"
            result["metadata"]["search_subject"] = search_result.get("metadata", {}).get("search_subject")
            result["metadata"]["video_found_by"] = search_result.get("metadata", {}).get("search_method", "semantic_search")
            result["metadata"]["videos_found_count"] = video_count
        else:
            # No videos found - return search results (which will show "no videos found")
            logger.info("No videos found - returning empty search result")
            result = search_result
    elif intent == "video_load":
        result = await compiled_video_load_flow.ainvoke(state)
    else:
        # Unknown intent - log warning and default to chitchat
        logger.warning(f"Unknown intent '{intent}', defaulting to chitchat flow")
        result = await compiled_chitchat_flow.ainvoke(state)

    logger.info(f"RAG flow completed successfully - response type: {result.get('metadata', {}).get('response_type', 'unknown')}")

    return result
