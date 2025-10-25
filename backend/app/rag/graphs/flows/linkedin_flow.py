"""
LinkedIn Flow for LangGraph

RAG flow for generating LinkedIn posts with topic extraction.
Similar to Q&A flow but uses LinkedIn-specific template.
"""

from loguru import logger
from typing import Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy

from app.rag.utils.state import GraphState
from app.rag.nodes.retriever import retrieve_chunks
from app.rag.nodes.grader import grade_chunks
from app.rag.nodes.generator import generate_response


# RetryPolicy for nodes with external dependencies
# Same configuration as Q&A flow: retriever (Qdrant + DB) and grader (LLM)
retry_policy = RetryPolicy(
    max_attempts=3,
    backoff_factor=2.0,  # Exponential backoff (2^n)
    initial_interval=1.0,
    max_interval=10.0,
    jitter=True  # Add randomness to prevent thundering herd
)


def build_linkedin_flow() -> StateGraph:
    """
    Build the LinkedIn post generation flow with RAG.

    This flow implements the RAG pipeline for LinkedIn content:
    1. Retrieve relevant chunks from Qdrant (top-12)
    2. Grade chunks for relevance using LLM
    3. Generate LinkedIn post based on graded chunks

    RetryPolicy applied to:
    - retriever: Qdrant + PostgreSQL coordination
    - grader: LLM structured JSON output (can fail parsing)

    No retry for generator (text generation rarely fails, tenacity handles API errors).

    Flow:
        START → retriever → grader → generator → END

    Returns:
        Compiled StateGraph for LinkedIn flow

    Example:
        flow = build_linkedin_flow()
        result = await flow.ainvoke({
            "user_query": "Write a LinkedIn post about FastAPI",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "linkedin"
        })
    """
    # Create graph
    workflow = StateGraph(GraphState)

    # Add nodes with selective retry policies
    workflow.add_node("retriever", retrieve_chunks, retry=retry_policy)
    workflow.add_node("grader", grade_chunks, retry=retry_policy)
    workflow.add_node("generator", generate_response)  # No retry

    # Set entry point
    workflow.set_entry_point("retriever")

    # Connect nodes sequentially
    workflow.add_edge("retriever", "grader")
    workflow.add_edge("grader", "generator")
    workflow.add_edge("generator", END)

    # Compile and return
    return workflow.compile()


# Export compiled graph for easy import
compiled_linkedin_flow = build_linkedin_flow()


async def run_linkedin_flow(state: GraphState) -> Dict[str, Any]:
    """
    Run the LinkedIn flow with the given state.

    Convenience function that invokes the compiled LinkedIn graph.

    Args:
        state: GraphState with user_query, user_id, conversation_history, intent

    Returns:
        Updated state with:
            - retrieved_chunks: Raw chunks from Qdrant
            - graded_chunks: Filtered relevant chunks
            - response: Generated LinkedIn post
            - metadata: Response metadata with sources

    Example:
        result = await run_linkedin_flow({
            "user_query": "Write a post about dependency injection",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "linkedin"
        })
        print(result["response"])
        print(result["metadata"]["chunks_used"])
    """
    logger.info(f"Running LinkedIn flow for query: {state.get('user_query', '')[:50]}...")
    result = await compiled_linkedin_flow.ainvoke(state)
    logger.info(
        f"LinkedIn flow completed - chunks used: {result.get('metadata', {}).get('chunks_used', 0)}"
    )
    return result
