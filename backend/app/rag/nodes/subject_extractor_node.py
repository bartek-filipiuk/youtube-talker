"""
Subject Extractor Node for LangGraph

Extracts the main subject/topic from user query when searching for videos.
Uses Gemini 2.5 Flash for structured JSON output.
"""

from typing import Dict, Any

from loguru import logger

from app.rag.utils.state import GraphState
from app.rag.utils.llm_client import LLMClient
from app.rag.utils.prompt_loader import render_prompt
from app.schemas.llm_responses import SubjectExtraction


async def extract_subject(state: GraphState) -> Dict[str, Any]:
    """
    Subject extractor node that extracts the main subject/topic from user query using LLM.

    This node is used in the metadata_search flow to identify what subject
    the user wants to filter videos by (e.g., "show videos about Claude Code").

    Args:
        state: Current graph state containing:
            - user_query: The user's input text
            - conversation_history: Last N messages for context

    Returns:
        Updated state with:
            - subject: Extracted subject string
            - metadata: Dict with confidence score and reasoning

    Raises:
        ValueError: If LLM returns invalid JSON or subject
        Exception: If LLM API call fails

    Example:
        state = {
            "user_query": "Show me videos about Claude Code",
            "user_id": "user123",
            "conversation_history": []
        }
        updated_state = await extract_subject(state)
        # updated_state["subject"] == "Claude Code"
    """
    user_query = state.get("user_query", "")
    user_id = state.get("user_id")
    conversation_history = state.get("conversation_history", [])

    logger.info(f"Extracting subject from query: {user_query[:50]}...")

    # Render prompt template
    prompt = render_prompt(
        "subject_extractor.jinja2",
        user_query=user_query,
        conversation_history=conversation_history
    )

    # Call LLM for structured output with user_id for LangSmith tracking
    llm_client = LLMClient()
    extraction = await llm_client.ainvoke_gemini_structured(
        prompt=prompt,
        schema=SubjectExtraction,
        user_id=user_id,  # Pass user_id for cost tracking
        temperature=0.3  # Low temperature for deterministic extraction
    )

    logger.info(
        f"Subject extracted as '{extraction.subject}' "
        f"with confidence {extraction.confidence:.2f}"
    )
    logger.debug(f"Reasoning: {extraction.reasoning}")

    # Update state
    return {
        **state,
        "subject": extraction.subject,
        "metadata": {
            **(state.get("metadata", {})),
            "subject_confidence": extraction.confidence,
            "subject_reasoning": extraction.reasoning
        }
    }
