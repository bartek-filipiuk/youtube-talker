"""
Chitchat Flow for LangGraph

Simple conversational flow without RAG retrieval.
Just generates a friendly response using the generator node.
"""

import logging
from typing import Dict, Any

from langgraph.graph import StateGraph, END

from app.rag.utils.state import GraphState
from app.rag.nodes.generator import generate_response

logger = logging.getLogger(__name__)


def build_chitchat_flow() -> StateGraph:
    """
    Build the chitchat flow graph.

    This is the simplest flow - just generates a conversational response
    without any RAG retrieval or grading.

    Flow:
        START → generator → END

    Returns:
        Compiled StateGraph for chitchat flow

    Example:
        flow = build_chitchat_flow()
        result = await flow.ainvoke({
            "user_query": "Hello!",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "chitchat"
        })
    """
    # Create graph
    workflow = StateGraph(GraphState)

    # Add generator node (no retry needed for text generation)
    workflow.add_node("generator", generate_response)

    # Set entry point
    workflow.set_entry_point("generator")

    # Generator goes directly to END
    workflow.add_edge("generator", END)

    # Compile and return
    return workflow.compile()


# Export compiled graph for easy import
compiled_chitchat_flow = build_chitchat_flow()


async def run_chitchat_flow(state: GraphState) -> Dict[str, Any]:
    """
    Run the chitchat flow with the given state.

    Convenience function that invokes the compiled chitchat graph.

    Args:
        state: GraphState with user_query, user_id, conversation_history, intent

    Returns:
        Updated state with response and metadata

    Example:
        result = await run_chitchat_flow({
            "user_query": "How are you?",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "chitchat"
        })
        print(result["response"])
    """
    logger.info(f"Running chitchat flow for query: {state.get('user_query', '')[:50]}...")
    result = await compiled_chitchat_flow.ainvoke(state)
    logger.info("Chitchat flow completed")
    return result
