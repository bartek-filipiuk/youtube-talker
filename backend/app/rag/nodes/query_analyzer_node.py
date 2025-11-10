"""
Query Analyzer Node for LangGraph (Phase 1 - Intelligent Search Pipeline)

Analyzes user queries to extract search signals for optimized video retrieval.
Extracts title keywords, topic keywords, alternative phrasings, and query intent.
"""

from typing import Dict, Any

from loguru import logger

from app.rag.utils.state import GraphState
from app.rag.utils.llm_client import LLMClient
from app.rag.utils.prompt_loader import render_prompt
from app.schemas.llm_responses import QueryAnalysis


async def analyze_query(state: GraphState) -> Dict[str, Any]:
    """
    Query analyzer node that extracts search signals from user query.

    Analyzes the query to extract:
    - title_keywords: Words/phrases from video title mentions
    - topic_keywords: Main subject/concept keywords
    - alternative_phrasings: 2-3 query variations for better search recall
    - query_intent: Type of query (summary, question, comparison, search, other)

    Args:
        state: Current graph state containing:
            - user_query: The user's input text
            - conversation_history: List of previous messages
            - config: Optional configuration (model selection)

    Returns:
        Updated state with:
            - query_analysis: QueryAnalysis object with extracted signals
            - metadata: Updated with analysis metadata

    Example:
        state = {
            "user_query": "napisz streszczenie dla Miliony nowych komórek MÓZGU",
            "user_id": "user123",
            "conversation_history": []
        }
        updated_state = await analyze_query(state)
        # updated_state["query_analysis"] contains extracted signals
    """
    user_query = state.get("user_query", "")
    user_id = state.get("user_id")
    conversation_history = state.get("conversation_history", [])
    config = state.get("config", {})
    model = config.get("model", "claude-haiku-4.5")  # Get model from config

    logger.info(f"Analyzing query for search signals: {user_query[:50]}... using model={model}")

    # Render prompt template
    prompt = render_prompt(
        "query_analyzer.jinja2",
        user_query=user_query,
        conversation_history=conversation_history
    )

    # Call LLM for structured output with dynamic model selection
    llm_client = LLMClient()
    analysis = await llm_client.ainvoke_structured(
        prompt=prompt,
        schema=QueryAnalysis,
        model=model,  # Use conversation-specific model
        user_id=user_id,  # Pass user_id for cost tracking
        temperature=0.3  # Low temperature for deterministic analysis
    )

    logger.info(
        f"Query analysis completed: "
        f"title_keywords={analysis.title_keywords}, "
        f"topic_keywords={analysis.topic_keywords}, "
        f"intent={analysis.query_intent}, "
        f"confidence={analysis.confidence:.2f}"
    )
    logger.debug(f"Alternative phrasings: {analysis.alternative_phrasings}")
    logger.debug(f"Reasoning: {analysis.reasoning}")

    # Update state
    return {
        **state,
        "query_analysis": analysis,
        "metadata": {
            **(state.get("metadata", {})),
            "query_analysis_confidence": analysis.confidence,
            "query_analysis_intent": analysis.query_intent,
            "has_title_keywords": len(analysis.title_keywords) > 0,
            "has_topic_keywords": len(analysis.topic_keywords) > 0
        }
    }
