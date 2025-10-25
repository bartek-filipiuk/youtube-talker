"""Grader node for RAG pipeline.

Binary relevance classification: determines if retrieved chunks are relevant to user query.
Uses Gemini 2.5 Flash with structured output (RelevanceGrade schema).
"""

from typing import Dict, List

from loguru import logger

from app.rag.utils.state import GraphState
from app.rag.utils.llm_client import LLMClient
from app.rag.utils.prompt_loader import render_prompt
from app.schemas.llm_responses import RelevanceGrade


async def grade_chunks(state: GraphState) -> GraphState:
    """
    Grader node: Binary relevance classification for retrieved chunks.

    Flow:
        1. Extract user_query and retrieved_chunks from state
        2. For each chunk:
           - Render chunk_grader.jinja2 template
           - Call LLMClient.ainvoke_gemini_structured(RelevanceGrade)
           - Binary classification: is_relevant (True/False)
        3. Keep only relevant chunks
        4. Store in state["graded_chunks"]

    Args:
        state: Current graph state with user_query and retrieved_chunks

    Returns:
        Updated state with graded_chunks field:
        [
            {
                "chunk_id": str,
                "chunk_text": str,
                "chunk_index": int,
                "youtube_video_id": str,
                "score": float,
                "relevance_reasoning": str  # Added by grader
            },
            ...
        ]

    State Updates:
        - state["graded_chunks"]: List of relevant chunks only
        - state["metadata"]["graded_count"]: Total chunks graded
        - state["metadata"]["relevant_count"]: Chunks marked relevant
        - state["metadata"]["not_relevant_count"]: Chunks filtered out

    Edge Cases:
        - Empty retrieved_chunks: Sets graded_chunks=[], continues gracefully
        - All chunks not relevant: Sets graded_chunks=[], metadata flag
        - LLM error: Logs error, skips chunk, continues with others
    """
    user_query = state.get("user_query")
    retrieved_chunks = state.get("retrieved_chunks", [])

    if not user_query:
        logger.warning("Missing user_query in state")
        state["graded_chunks"] = []
        return state

    if not retrieved_chunks:
        logger.info("No retrieved chunks to grade")
        state["graded_chunks"] = []
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["graded_count"] = 0
        state["metadata"]["relevant_count"] = 0
        state["metadata"]["not_relevant_count"] = 0
        return state

    logger.info(f"Grading {len(retrieved_chunks)} chunks for relevance")

    llm_client = LLMClient()
    graded_chunks = []
    relevant_count = 0
    not_relevant_count = 0

    # Grade each chunk individually (12 LLM calls for top-12)
    for chunk in retrieved_chunks:
        try:
            # Render grading prompt
            prompt = render_prompt(
                "chunk_grader.jinja2",
                user_query=user_query,
                chunk_text=chunk["chunk_text"],
                chunk_metadata={
                    "youtube_video_id": chunk["youtube_video_id"],
                    "chunk_index": chunk["chunk_index"],
                },
            )

            # Call Gemini for structured output
            grade: RelevanceGrade = await llm_client.ainvoke_gemini_structured(
                prompt=prompt,
                schema=RelevanceGrade,
            )

            # Keep only relevant chunks
            if grade.is_relevant:
                graded_chunk = {
                    **chunk,  # Keep all original fields
                    "relevance_reasoning": grade.reasoning,  # Add grader reasoning
                }
                graded_chunks.append(graded_chunk)
                relevant_count += 1
                logger.debug(
                    f"✓ Chunk {chunk['chunk_index']} relevant: {grade.reasoning[:50]}..."
                )
            else:
                not_relevant_count += 1
                logger.debug(
                    f"✗ Chunk {chunk['chunk_index']} not relevant: {grade.reasoning[:50]}..."
                )

        except Exception as e:
            logger.exception(
                f"Error grading chunk {chunk.get('chunk_index', 'unknown')}: {e}"
            )
            # Skip this chunk, continue with others
            not_relevant_count += 1
            continue

    # Update state
    state["graded_chunks"] = graded_chunks
    if "metadata" not in state:
        state["metadata"] = {}
    state["metadata"]["graded_count"] = len(retrieved_chunks)
    state["metadata"]["relevant_count"] = relevant_count
    state["metadata"]["not_relevant_count"] = not_relevant_count

    logger.info(
        f"Grading complete: {relevant_count} relevant, {not_relevant_count} filtered out"
    )

    # Warn if no relevant chunks found
    if relevant_count == 0:
        logger.warning("No relevant chunks found after grading")
        state["metadata"]["no_relevant_chunks"] = True

    return state
