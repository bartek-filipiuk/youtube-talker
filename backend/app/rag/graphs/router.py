"""
Main Router for LangGraph Flows

Orchestrates intent classification and routing to appropriate flow.
Entry point for all RAG operations.
"""

import logging
from typing import Dict, Any

from app.rag.utils.state import GraphState
from app.rag.nodes.router_node import classify_intent
from app.rag.graphs.flows.chitchat_flow import compiled_chitchat_flow
from app.rag.graphs.flows.qa_flow import compiled_qa_flow
from app.rag.graphs.flows.linkedin_flow import compiled_linkedin_flow
from app.rag.graphs.flows.metadata_flow import compiled_metadata_flow

logger = logging.getLogger(__name__)


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
    2. Route to appropriate flow (chitchat, qa, linkedin, or metadata)
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
            - intent: Classified intent ("chitchat", "qa", "linkedin", or "metadata")
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
    state: GraphState = {
        "user_query": user_query,
        "user_id": user_id,
        "conversation_history": conversation_history,
        "config": config or {}
    }

    logger.info(f"Starting RAG flow for user {user_id}: {user_query[:50]}...")

    # Step 1: Classify intent
    state = await classify_intent(state)
    intent = state.get("intent")

    if not intent:
        raise ValueError("Intent classification failed - no intent returned")

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
    else:
        # Unknown intent - log warning and default to chitchat
        logger.warning(f"Unknown intent '{intent}', defaulting to chitchat flow")
        result = await compiled_chitchat_flow.ainvoke(state)

    logger.info(f"RAG flow completed successfully - response type: {result.get('metadata', {}).get('response_type', 'unknown')}")

    return result
