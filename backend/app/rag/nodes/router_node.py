"""
Router Node for LangGraph (V2 - Simplified 3-Intent System)

Classifies user intent into 3 categories:
- "system": System operations (URLs, list commands)
- "linkedin": LinkedIn post creation (explicit mention required)
- "content": Everything else (questions, searches, chitchat)

Uses Claude Haiku 4.5 for structured JSON output.
"""

from typing import Dict, Any

from loguru import logger

from app.rag.utils.state import GraphState
from app.rag.utils.llm_client import LLMClient
from app.rag.utils.prompt_loader import render_prompt
from app.schemas.llm_responses import IntentClassification


async def classify_intent(state: GraphState) -> Dict[str, Any]:
    """
    Router node that classifies user intent using simplified 3-intent system.

    Intents:
    - "system": System operations (YouTube URLs, list commands)
    - "linkedin": LinkedIn post creation (MUST explicitly mention "LinkedIn")
    - "content": Everything else (default - questions, searches, chitchat)

    Args:
        state: Current graph state containing:
            - user_query: The user's input text
            - conversation_history: List of previous messages

    Returns:
        Updated state with:
            - intent: Classified intent string ("system"|"linkedin"|"content")
            - metadata: Dict with confidence score and reasoning

    Example:
        state = {
            "user_query": "napisz cos o mitach programowania z AI",
            "user_id": "user123",
            "conversation_history": []
        }
        updated_state = await classify_intent(state)
        # updated_state["intent"] == "content"
    """
    user_query = state.get("user_query", "")
    user_id = state.get("user_id")
    conversation_history = state.get("conversation_history", [])

    logger.info(f"Classifying intent (V2 - 3 intents) for query: {user_query[:50]}...")

    # Render prompt template (V2 - simplified prompt)
    prompt = render_prompt(
        "query_router_v2.jinja2",
        user_query=user_query,
        conversation_history=conversation_history
    )

    # Call LLM for structured output with user_id for LangSmith tracking
    # Using Claude Haiku 4.5 for better reasoning on edge cases
    llm_client = LLMClient()
    classification = await llm_client.ainvoke_claude_structured(
        prompt=prompt,
        schema=IntentClassification,
        user_id=user_id,  # Pass user_id for cost tracking
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
