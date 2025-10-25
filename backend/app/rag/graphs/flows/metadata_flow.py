"""
Metadata Flow for LangGraph

Simple flow for handling metadata queries about available videos.
Just queries the database and returns formatted list - no RAG retrieval needed.
"""

from loguru import logger
from typing import Dict, Any

from langgraph.graph import StateGraph, END

from app.rag.utils.state import GraphState
from app.rag.nodes.metadata_node import get_user_videos



def build_metadata_flow() -> StateGraph:
    """
    Build the metadata flow graph.

    This is a simple flow - just queries the database for user's videos
    and returns a formatted list. No RAG retrieval or LLM generation needed.

    Flow:
        START → metadata_node → END

    Returns:
        Compiled StateGraph for metadata flow

    Example:
        flow = build_metadata_flow()
        result = await flow.ainvoke({
            "user_query": "What videos do I have?",
            "user_id": "user-uuid-here",
            "conversation_history": [],
            "intent": "metadata"
        })
    """
    # Create graph
    workflow = StateGraph(GraphState)

    # Add metadata node (queries database and formats response)
    workflow.add_node("metadata_node", get_user_videos)

    # Set entry point
    workflow.set_entry_point("metadata_node")

    # Metadata node goes directly to END
    workflow.add_edge("metadata_node", END)

    # Compile and return
    return workflow.compile()


# Export compiled graph for easy import
compiled_metadata_flow = build_metadata_flow()


async def run_metadata_flow(state: GraphState) -> Dict[str, Any]:
    """
    Run the metadata flow with the given state.

    Convenience function that invokes the compiled metadata graph.

    Args:
        state: GraphState with user_query, user_id, conversation_history, intent

    Returns:
        Updated state with response and metadata

    Example:
        result = await run_metadata_flow({
            "user_query": "Show me my videos",
            "user_id": "user-uuid-here",
            "conversation_history": [],
            "intent": "metadata"
        })
        print(result["response"])  # HTML list of videos
        print(result["metadata"]["video_count"])  # Number of videos
    """
    logger.info(f"Running metadata flow for query: {state.get('user_query', '')[:50]}...")
    result = await compiled_metadata_flow.ainvoke(state)
    logger.info(f"Metadata flow completed - found {result.get('metadata', {}).get('video_count', 0)} videos")
    return result
