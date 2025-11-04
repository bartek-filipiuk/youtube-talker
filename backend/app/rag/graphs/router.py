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

        # Check if exactly 1 video was found
        video_count = search_result.get("metadata", {}).get("video_count", 0)

        if video_count == 1:
            logger.info("Single video found - auto-generating summary via QA flow")

            # STAGE 2: Auto-generate summary using QA flow
            # Update user_query to trigger summary generation
            qa_state = {
                **search_result,
                "user_query": "Summarize the main points and key information from this video",
                "intent": "qa"  # Override to qa for generation
            }
            result = await compiled_qa_flow.ainvoke(qa_state)

            # Preserve original search metadata
            result["metadata"]["original_intent"] = "metadata_search_and_summarize"
            result["metadata"]["search_subject"] = search_result.get("metadata", {}).get("search_subject")
            result["metadata"]["video_found_by"] = search_result.get("metadata", {}).get("search_method", "semantic_search")
        else:
            # Multiple or zero videos - return search results with guidance
            logger.info(f"Found {video_count} videos - returning search results with guidance")
            result = search_result
    elif intent == "video_load":
        result = await compiled_video_load_flow.ainvoke(state)
    else:
        # Unknown intent - log warning and default to chitchat
        logger.warning(f"Unknown intent '{intent}', defaulting to chitchat flow")
        result = await compiled_chitchat_flow.ainvoke(state)

    logger.info(f"RAG flow completed successfully - response type: {result.get('metadata', {}).get('response_type', 'unknown')}")

    return result
