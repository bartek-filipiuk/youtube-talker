"""
Generator Node for LangGraph

Generates final responses based on intent and graded chunks.
Uses Claude Haiku 4.5 for natural text generation.
"""

from typing import Dict, Any, List

from loguru import logger

from app.rag.utils.state import GraphState
from app.rag.utils.llm_client import LLMClient
from app.rag.utils.prompt_loader import render_prompt


async def generate_response(state: GraphState) -> Dict[str, Any]:
    """
    Generator node that creates final response based on intent.

    Routes to appropriate prompt template based on classified intent:
    - chitchat: Simple conversational response (no RAG context)
    - qa: Answer using graded chunks from RAG
    - linkedin: Generate LinkedIn post using graded chunks

    Args:
        state: Current graph state containing:
            - intent: Classified intent ("chitchat" | "qa" | "linkedin")
            - user_query: The user's input text
            - conversation_history: Last N messages for context
            - graded_chunks: (optional) Relevant chunks after grading

    Returns:
        Updated state with:
            - response: Generated text response
            - metadata: Dict with response metadata (sources, chunk count, etc.)

    Raises:
        ValueError: If intent is missing
        KeyError: If required state fields are missing
        Exception: If LLM API call fails

    Note:
        Unknown intents will default to chitchat as a fallback behavior.

    Example:
        state = {
            "intent": "qa",
            "user_query": "What is FastAPI?",
            "user_id": "user123",
            "conversation_history": [],
            "graded_chunks": [{"chunk_text": "FastAPI is...", "metadata": {...}}]
        }
        updated_state = await generate_response(state)
        # updated_state["response"] contains the generated answer
    """
    # Default to "chitchat" if intent not set by router (defensive fallback)
    intent = state.get("intent", "chitchat")
    user_query = state.get("user_query", "")
    user_id = state.get("user_id")
    conversation_history = state.get("conversation_history", [])
    graded_chunks = state.get("graded_chunks", [])
    config = state.get("config", {})
    model = config.get("model", "claude-haiku-4.5")  # Get model from config

    logger.info(f"Generating response for intent: {intent} using model={model}")

    # Initialize LLM client
    llm_client = LLMClient()

    # Route to appropriate template based on intent
    if intent == "chitchat":
        prompt = render_prompt(
            "chitchat_flow.jinja2",
            user_query=user_query,
            conversation_history=conversation_history
        )
        response = await llm_client.ainvoke(
            prompt=prompt,
            model=model,  # Use conversation-specific model
            user_id=user_id,  # Pass user_id for cost tracking
            max_tokens=500,  # Shorter for chitchat
            temperature=0.8  # More creative for conversation
        )
        metadata = {
            **(state.get("metadata", {})),
            "response_type": "chitchat",
            "chunks_used": 0
        }

    elif intent == "qa":
        if not graded_chunks:
            logger.warning("No graded chunks available for Q&A, using empty context")

        prompt = render_prompt(
            "rag_qa.jinja2",
            user_query=user_query,
            conversation_history=conversation_history,
            graded_chunks=graded_chunks
        )
        response = await llm_client.ainvoke(
            prompt=prompt,
            model=model,  # Use conversation-specific model
            user_id=user_id,  # Pass user_id for cost tracking
            max_tokens=2000,
            temperature=0.7  # Balanced for factual Q&A
        )
        metadata = {
            **(state.get("metadata", {})),
            "response_type": "qa",
            "chunks_used": len(graded_chunks),
            "source_chunks": _extract_chunk_ids(graded_chunks)
        }

    elif intent == "linkedin":
        if not graded_chunks:
            logger.warning("No graded chunks available for LinkedIn post generation")

        # Extract topic from user query (simple approach for MVP)
        topic = user_query.replace("write a linkedin post about", "").strip()
        topic = topic.replace("create a linkedin post about", "").strip()
        topic = topic.replace("generate a linkedin post about", "").strip()

        prompt = render_prompt(
            "linkedin_post_generate.jinja2",
            topic=topic or user_query,
            conversation_history=conversation_history,
            graded_chunks=graded_chunks
        )
        response = await llm_client.ainvoke(
            prompt=prompt,
            model=model,  # Use conversation-specific model
            user_id=user_id,  # Pass user_id for cost tracking
            max_tokens=2000,
            temperature=0.75  # Slightly creative for engaging content
        )
        metadata = {
            **(state.get("metadata", {})),
            "response_type": "linkedin",
            "chunks_used": len(graded_chunks),
            "source_chunks": _extract_chunk_ids(graded_chunks),
            "topic": topic or user_query
        }

    else:
        # Unknown intent - default to chitchat as fallback
        logger.warning(f"Unknown intent '{intent}', defaulting to chitchat")
        prompt = render_prompt(
            "chitchat_flow.jinja2",
            user_query=user_query,
            conversation_history=conversation_history
        )
        response = await llm_client.ainvoke(
            prompt=prompt,
            model=model,  # Use conversation-specific model
            user_id=user_id,  # Pass user_id for cost tracking
            max_tokens=500,
            temperature=0.8
        )
        metadata = {
            **(state.get("metadata", {})),
            "response_type": "chitchat",
            "chunks_used": 0,
            "fallback_from_unknown_intent": intent  # Track that we fell back
        }

    logger.info(
        f"Generated response for {intent} "
        f"(length: {len(response)}, chunks: {len(graded_chunks)})"
    )

    # Update state
    return {
        **state,
        "response": response,
        "metadata": metadata
    }


def _extract_chunk_ids(chunks: List[Dict]) -> List[str]:
    """
    Extract chunk IDs from graded chunks for metadata tracking.

    Args:
        chunks: List of graded chunk dictionaries

    Returns:
        List of chunk IDs (empty list if no IDs found)
    """
    chunk_ids = []
    for chunk in chunks:
        # Try different possible locations for chunk ID
        chunk_id = (
            chunk.get("id") or
            chunk.get("chunk_id") or
            chunk.get("metadata", {}).get("chunk_id")
        )
        if chunk_id:
            chunk_ids.append(str(chunk_id))

    return chunk_ids
