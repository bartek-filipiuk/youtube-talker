"""
Q&A Flow for LangGraph

Full RAG flow with retrieval, grading, and generation.
Includes retry policies for nodes with external dependencies.
"""

from loguru import logger
from typing import Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy

from app.rag.utils.state import GraphState
from app.rag.nodes.retriever import retrieve_chunks
from app.rag.nodes.grader import grade_chunks
from app.rag.nodes.generator import generate_response


# RetryPolicy for nodes with external dependencies or coordination
# Applied to retriever (Qdrant + DB) and grader (LLM structured output)
retry_policy = RetryPolicy(
    max_attempts=3,
    backoff_factor=2.0,  # Exponential backoff (2^n)
    initial_interval=1.0,
    max_interval=10.0,
    jitter=True  # Add randomness to prevent thundering herd
)


def build_qa_flow() -> StateGraph:
    """
    Build the Q&A flow graph with RAG retrieval and grading.

    This flow implements the full RAG pipeline:
    1. Retrieve relevant chunks from Qdrant (top-12)
    2. Grade chunks for relevance using LLM
    3. Generate answer based on graded chunks

    RetryPolicy applied to:
    - retriever: Qdrant + PostgreSQL coordination
    - grader: LLM structured JSON output (can fail parsing)

    No retry for generator (text generation rarely fails, tenacity handles API errors).

    Flow:
        START → retriever → grader → generator → END

    Returns:
        Compiled StateGraph for Q&A flow

    Example:
        flow = build_qa_flow()
        result = await flow.ainvoke({
            "user_query": "What is FastAPI?",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "qa"
        })
    """
    # Create graph
    workflow = StateGraph(GraphState)

    # Add nodes with selective retry policies
    workflow.add_node("retriever", retrieve_chunks, retry_policy=retry_policy)
    workflow.add_node("grader", grade_chunks, retry_policy=retry_policy)
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
compiled_qa_flow = build_qa_flow()


async def run_qa_flow(state: GraphState) -> Dict[str, Any]:
    """
    Run the Q&A flow with the given state.

    Convenience function that invokes the compiled Q&A graph.

    Args:
        state: GraphState with user_query, user_id, conversation_history, intent

    Returns:
        Updated state with:
            - retrieved_chunks: Raw chunks from Qdrant
            - graded_chunks: Filtered relevant chunks
            - response: Generated answer
            - metadata: Response metadata with sources

    Example:
        result = await run_qa_flow({
            "user_query": "What is dependency injection?",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "qa"
        })
        print(result["response"])
        print(result["metadata"]["chunks_used"])
    """
    logger.info(f"Running Q&A flow for query: {state.get('user_query', '')[:50]}...")
    result = await compiled_qa_flow.ainvoke(state)
    logger.info(
        f"Q&A flow completed - chunks used: {result.get('metadata', {}).get('chunks_used', 0)}"
    )
    return result
