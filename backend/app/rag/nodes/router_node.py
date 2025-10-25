"""
Router Node for LangGraph

Classifies user intent to route to appropriate flow.
Uses Gemini 2.5 Flash for structured JSON output.
"""

from typing import Dict, Any

from loguru import logger

from app.rag.utils.state import GraphState
from app.rag.utils.llm_client import LLMClient
from app.rag.utils.prompt_loader import render_prompt
from app.schemas.llm_responses import IntentClassification


async def classify_intent(state: GraphState) -> Dict[str, Any]:
    """
    Router node that classifies user intent using LLM.

    This node determines which flow to execute based on the user's query:
    - "chitchat": Casual conversation (no RAG needed)
    - "qa": Question-answering (requires RAG retrieval)
    - "linkedin": LinkedIn post generation (requires RAG retrieval)

    Args:
        state: Current graph state containing:
            - user_query: The user's input text
            - conversation_history: Last N messages for context

    Returns:
        Updated state with:
            - intent: Classified intent string
            - metadata: Dict with confidence score and reasoning

    Raises:
        ValueError: If LLM returns invalid JSON or intent
        Exception: If LLM API call fails

    Example:
        state = {
            "user_query": "Write a LinkedIn post about FastAPI",
            "user_id": "user123",
            "conversation_history": []
        }
        updated_state = await classify_intent(state)
        # updated_state["intent"] == "linkedin"
    """
    user_query = state.get("user_query", "")
    conversation_history = state.get("conversation_history", [])

    logger.info(f"Classifying intent for query: {user_query[:50]}...")

    # Render prompt template
    prompt = render_prompt(
        "query_router.jinja2",
        user_query=user_query,
        conversation_history=conversation_history
    )

    # Call LLM for structured output
    llm_client = LLMClient()
    classification = await llm_client.ainvoke_gemini_structured(
        prompt=prompt,
        schema=IntentClassification,
        temperature=0.3  # Low temperature for deterministic classification
    )

    logger.info(
        f"Intent classified as '{classification.intent}' "
        f"with confidence {classification.confidence:.2f}"
    )
    logger.debug(f"Reasoning: {classification.reasoning}")

    # Update state
    return {
        **state,
        "intent": classification.intent,
        "metadata": {
            **(state.get("metadata", {})),
            "intent_confidence": classification.confidence,
            "intent_reasoning": classification.reasoning
        }
    }
