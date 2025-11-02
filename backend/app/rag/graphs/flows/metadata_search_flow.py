"""
Metadata Search Flow for LangGraph

Handles subject-based video search with semantic matching.
Extracts subject from query, then searches Qdrant for matching videos.
"""

from loguru import logger
from typing import Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy

from app.rag.utils.state import GraphState
from app.rag.nodes.subject_extractor_node import extract_subject
from app.rag.nodes.video_search_node import search_videos_by_subject


# RetryPolicy for nodes with external dependencies
# Applied to both subject extractor (LLM) and video search (Qdrant + DB)
retry_policy = RetryPolicy(
    max_attempts=3,
    backoff_factor=2.0,  # Exponential backoff (2^n)
    initial_interval=1.0,
    max_interval=10.0,
    jitter=True  # Add randomness to prevent thundering herd
)


def build_metadata_search_flow() -> StateGraph:
    """
    Build the metadata search flow graph.

    This flow implements subject-based video search:
    1. Extract subject/topic from user query using LLM
    2. Search Qdrant for matching video chunks
    3. Rank videos by relevance and return top 20

    RetryPolicy applied to:
    - subject_extractor: LLM structured JSON output (can fail parsing)
    - video_search: Qdrant + PostgreSQL coordination

    Flow:
        START → subject_extractor → video_search → END

    Returns:
        Compiled StateGraph for metadata search flow

    Example:
        flow = build_metadata_search_flow()
        result = await flow.ainvoke({
            "user_query": "Show me videos about Claude Code",
            "user_id": "user-uuid-here",
            "conversation_history": [],
            "intent": "metadata_search"
        })
    """
    # Create graph
    workflow = StateGraph(GraphState)

    # Add nodes with retry policies
    workflow.add_node("subject_extractor", extract_subject, retry_policy=retry_policy)
    workflow.add_node("video_search", search_videos_by_subject, retry_policy=retry_policy)

    # Set entry point
    workflow.set_entry_point("subject_extractor")

    # Connect nodes sequentially
    workflow.add_edge("subject_extractor", "video_search")
    workflow.add_edge("video_search", END)

    # Compile and return
    return workflow.compile()


# Export compiled graph for easy import
compiled_metadata_search_flow = build_metadata_search_flow()


async def run_metadata_search_flow(state: GraphState) -> Dict[str, Any]:
    """
    Run the metadata search flow with the given state.

    Convenience function that invokes the compiled metadata search graph.

    Args:
        state: GraphState with user_query, user_id, conversation_history, intent

    Returns:
        Updated state with response and metadata

    Example:
        result = await run_metadata_search_flow({
            "user_query": "Find videos about FastAPI",
            "user_id": "user-uuid-here",
            "conversation_history": [],
            "intent": "metadata_search"
        })
        print(result["response"])  # HTML list of matching videos
        print(result["metadata"]["video_count"])  # Number of matching videos
        print(result["metadata"]["search_subject"])  # Extracted subject
    """
    logger.info(f"Running metadata search flow for query: {state.get('user_query', '')[:50]}...")
    result = await compiled_metadata_search_flow.ainvoke(state)
    logger.info(
        f"Metadata search flow completed - found {result.get('metadata', {}).get('video_count', 0)} videos "
        f"for subject '{result.get('metadata', {}).get('search_subject', 'N/A')}'"
    )
    return result
