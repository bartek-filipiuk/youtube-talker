"""
Main Router for LangGraph Flows (V2 - Simplified 3-Intent System)

Orchestrates intent classification and routing to appropriate flow.
Entry point for all RAG operations.

Architecture:
- 3 intents only: system, linkedin, content
- Content handler does semantic search + smart routing
- No more complex compound flows or proactive fallbacks
"""

from loguru import logger
from typing import Dict, Any

from app.rag.utils.state import GraphState
from app.rag.nodes.router_node import classify_intent
from app.rag.nodes.system_router_node import route_system_operation
from app.rag.nodes.content_handler_node import handle_content_query
from app.rag.graphs.flows.linkedin_flow import compiled_linkedin_flow


async def run_graph(
    user_query: str,
    user_id: str,
    conversation_history: list,
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Main entry point for RAG system (V2 - Simplified Architecture).

    Orchestrates the complete flow:
    1. Classify user intent (3 categories: system, linkedin, content)
    2. Route to appropriate handler
    3. Return final state with response

    Args:
        user_query: The user's input text
        user_id: User identifier for personalization
        conversation_history: List of previous messages for context
        config: Optional runtime configuration

    Returns:
        Final GraphState containing:
            - user_query: Original query
            - user_id: User identifier
            - conversation_history: Conversation context
            - intent: Classified intent ("system"|"linkedin"|"content")
            - response: Generated response (HTML formatted)
            - metadata: Response metadata including:
                - intent_confidence: Router confidence score
                - intent_reasoning: Router reasoning
                - routing_decision: How the query was handled

    Raises:
        ValueError: If intent classification fails or returns unknown intent
        Exception: If any handler fails

    Example:
        result = await run_graph(
            user_query="napisz cos o mitach programowania z AI",
            user_id="user123",
            conversation_history=[],
            config={"top_k": 12}
        )
        print(result["response"])  # HTML response
        print(result["intent"])     # "content"
        print(result["metadata"]["routing_decision"])  # "generate"
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

    logger.info(f"Starting RAG flow (V2) for user {user_id}: {user_query[:50]}...")

    # Step 1: Classify intent (3 categories)
    state = await classify_intent(state)
    intent = state.get("intent")

    if not intent:
        raise ValueError("Intent classification failed - no intent returned")

    # Validate intent is recognized
    VALID_INTENTS = {"system", "linkedin", "content"}

    if intent not in VALID_INTENTS:
        logger.error(
            f"Invalid intent '{intent}' returned by LLM. "
            f"Valid intents: {VALID_INTENTS}. "
            f"Defaulting to content handler."
        )
        # Store original invalid intent for debugging
        original_intent = intent
        intent = "content"
        state["intent"] = "content"

        # Add error metadata
        metadata = state.get("metadata", {})
        metadata["intent_error"] = True
        metadata["original_invalid_intent"] = original_intent
        state["metadata"] = metadata

    logger.info(
        f"Intent classified as '{intent}' with confidence "
        f"{state.get('metadata', {}).get('intent_confidence', 0):.2f}"
    )

    # Step 2: Route to appropriate handler
    try:
        if intent == "system":
            # System operations (YouTube URLs, list commands)
            logger.info("Routing to system operation handler")
            result = await route_system_operation(state)

        elif intent == "linkedin":
            # LinkedIn post generation (explicit mention required)
            logger.info("Routing to LinkedIn flow")
            result = await compiled_linkedin_flow.ainvoke(state)

        else:  # content (default)
            # Content queries (questions, searches, chitchat)
            # Handler performs semantic search and routes based on scores
            logger.info("Routing to content handler (unified qa/search/chitchat)")
            result = await handle_content_query(state)

        logger.info(
            f"RAG flow (V2) completed successfully - "
            f"response type: {result.get('metadata', {}).get('response_type', 'unknown')}"
        )

        return result

    except Exception as e:
        logger.exception(f"Error in routing flow: {e}")
        raise
